from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_classic.chains import RetrievalQA
from langchain_classic.agents import tool, AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from app.model import load_model
from langchain_classic.memory import ConversationBufferMemory

import chromadb
from chromadb.config import Settings
import os

os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"



def format_sources(source_documents):
    """Format source documents with document name, page numbers, and excerpts"""
    if not source_documents:
        return None
    
    formatted_sources = []
    for i, doc in enumerate(source_documents, 1):
        source_file = doc.metadata.get("source_file", "Unknown")
        page_num = doc.metadata.get("page", "Unknown")
        content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
        
        formatted_sources.append({
            "source_number": i,
            "source_file": source_file,
            "page": page_num,
            "excerpt": content,
            "full_content": doc.page_content
        })
    
    return formatted_sources


def retrieve_documents(db, query: str, k: int = 6):
    retriever = db.as_retriever(search_kwargs={"k": k})
    return retriever.invoke(query)


def split_docs(documents):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200
    )
    return splitter.split_documents(documents)


def get_chroma_client(persist_directory: str = "db/chroma_db"):
    """Create a Chroma client with persistent local storage."""
    os.makedirs(persist_directory, exist_ok=True)
    settings = Settings(
        persist_directory=persist_directory,
        is_persistent=True,
        anonymized_telemetry=True
    )
    return chromadb.Client(settings=settings)


def create_vector_db(chunks):
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    import ssl
    os.environ['CURL_CA_BUNDLE'] = ''
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        pass
    else:
        ssl._create_default_https_context = _create_unverified_https_context
    
    embedding = HuggingFaceEmbeddings(
    model_name=r"C:\Users\HOMEPC\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
    )

    client = get_chroma_client("db/chroma_db")
    db = Chroma.from_documents(
        documents=chunks,
        embedding=embedding,
        persist_directory="db/chroma_db",
        client=client
    )

    return db


def load_vector_db():
    """Load saved vector store from disk — no PDF reading, no embedding"""
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    embedding = HuggingFaceEmbeddings(
    model_name=r"C:\Users\HOMEPC\.cache\huggingface\hub\models--sentence-transformers--all-MiniLM-L6-v2\snapshots\c9745ed1d9f207416be6d2e6f8de32d1f16199bf",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
    )

    client = get_chroma_client("db/chroma_db")
    db = Chroma(
        persist_directory="db/chroma_db",
        embedding_function=embedding,
        client=client
    )
    return db


def create_hybrid_retriever(chunks, db):
    """Simplified hybrid retrieval without EnsembleRetriever"""

    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 5

    semantic_retriever = db.as_retriever(search_kwargs={"k": 5})

    class HybridRetriever:
        def invoke(self, query):
            bm25_docs = bm25_retriever.invoke(query)
            semantic_docs = semantic_retriever.invoke(query)

            all_docs = bm25_docs + semantic_docs

            unique = []
            seen = set()

            for doc in all_docs:
                key = doc.page_content[:200]
                if key not in seen:
                    seen.add(key)
                    unique.append(doc)

            return unique[:7]

    return HybridRetriever()


def retrieve_context(db, query, k=3):
    docs = db.similarity_search(query, k=k)
    context = "\n\n".join([doc.page_content for doc in docs])
    return context


def rewrite_query(original_query: str, llm) -> list:
    rewrite_prompt = PromptTemplate.from_template("""
You are a query optimization expert. Generate 3 alternative ways to phrase this question to improve search results.

Original question: {query}

Generate 3 variations that:
1. Use synonyms
2. Break down complex questions into simpler parts
3. Add relevant context words

Format your response as a numbered list (1. variation, 2. variation, 3. variation).
Keep each variation concise and clear.
""")
    
    chain = rewrite_prompt | llm
    response = chain.invoke({"query": original_query})
    
    variations = []
    lines = response.split('\n')
    for line in lines:
        if line.strip() and any(line.strip().startswith(str(i)) for i in range(1, 4)):
            cleaned = line.strip()
            if cleaned[0].isdigit():
                cleaned = cleaned.split('. ', 1)[-1] if '. ' in cleaned else cleaned.split(') ', 1)[-1]
            if cleaned:
                variations.append(cleaned)
    
    all_queries = [original_query] + variations[:3]
    return all_queries[:4]


def retrieve_with_rewritten_queries(retriever, original_query: str, llm) -> list:
    query_variations = rewrite_query(original_query, llm)
    
    all_docs = []
    doc_ids = set()
    
    for query in query_variations:
        docs = retriever.invoke(query)
        for doc in docs:
            doc_id = hash(doc.page_content)
            if doc_id not in doc_ids:
                all_docs.append(doc)
                doc_ids.add(doc_id)
    
    return all_docs[:7]


def build_qa(db):
    llm = load_model()
    qa = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=db.as_retriever(search_kwargs={"k": 7}),
        chain_type="stuff",
        return_source_documents=True,
        verbose=True
    )
    return qa


def build_agent_based_qa(chunks, db):
    """Build an agent-based QA system with hybrid retrieval, query rewriting, and intelligent routing"""
    llm = load_model()
    
    retriever = create_hybrid_retriever(chunks, db)
    
    @tool
    def retrieve_from_documents(query: str) -> str:
        """Retrieve relevant information from the study documents using query rewriting"""
        try:
            docs = retrieve_with_rewritten_queries(retriever, query, llm)
        except:
            docs = retriever.invoke(query)
        
        if not docs:
            return "No relevant documents found."
        
        content = "\n\n".join([doc.page_content for doc in docs])
        return f"Found {len(docs)} relevant sections:\n\n{content}"
    
    @tool
    def search_multiple_sources(query: str) -> str:
        """Search for information across multiple document sections with query variations"""
        try:
            docs = retrieve_with_rewritten_queries(retriever, query, llm)
        except:
            docs = retriever.invoke(query)
        
        if len(docs) < 3:
            return f"Only {len(docs)} sources found. Document may have limited coverage on this topic."
        return f"Multiple sources found ({len(docs)}). Synthesizing information..."
    
    @tool
    def check_knowledge_limits(query: str) -> str:
        """Check if the query is beyond the document scope"""
        try:
            docs = retrieve_with_rewritten_queries(retriever, query, llm)
        except:
            docs = retriever.invoke(query)
        
        if not docs or len(docs) < 2:
            return "This topic appears to be outside the scope of the provided materials."
        return "Information available in documents."
    
    tools = [retrieve_from_documents, search_multiple_sources, check_knowledge_limits]
    
    agent_prompt = PromptTemplate.from_template("""
You are SMARTSTUDY, an intelligent study assistant.

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Rules:
- Always check knowledge limits first
- Cite sources from documents
- Be honest about gaps in knowledge
- Use multiple sources when available

Begin!

Question: {input}
Thought:{agent_scratchpad}
""")
    
    agent = create_react_agent(llm, tools, agent_prompt)
    
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True
    )
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    
    return agent_executor, retriever


def build_retrieval_qa(db):
    llm = load_model()

    retriever = db.as_retriever(search_kwargs={"k": 5})

    prompt = PromptTemplate.from_template("""You are SMARTSTUDY, a ZIMSEC tutor for Zimbabwean students.

STRICT RULES:
1. Read the context below carefully.
2. Answer ONLY using information from the context.
3. Do NOT use markdown. No **, no ##, no bullet symbols.
4. Do NOT add disclaimers or say "as an AI".
5. If the answer is not in the context, say exactly: Not found in notes.
6. Write in plain sentences. 2 to 4 sentences maximum.
7. Do not repeat the question back.

Context:
{context}

Question: {question}

Answer:""")

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=True,
        verbose=False,
        chain_type_kwargs={"prompt": prompt}
    )

    return qa_chain, retriever


def is_answer_grounded(answer: str) -> bool:
    """Check if answer appears to be based on provided context rather than hallucinated"""
    answer_lower = answer.lower()

    hallucination_signals = [
        "i think",
        "i believe",
        "generally speaking",
        "typically",
        "in general",
        "usually",
        "as far as i know",
        "from my knowledge",
        "i recall",
        "i remember",
        "based on my training",
        "as an ai",
    ]

    for signal in hallucination_signals:
        if signal in answer_lower:
            return False

    if len(answer.strip()) < 10:
        return False

    if "don't have information" in answer_lower or "not in my study materials" in answer_lower:
        return True

    return True