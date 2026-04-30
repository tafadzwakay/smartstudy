from langchain.document_loaders import TextLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import Ollama
from langchain.chains import RetrievalQA

system_prompt = """
You are SMARTSTUDY, a strict Zimbabwean AI tutor.

RULES:
- Answer ONLY using the provided context (notes/PDF)
- DO NOT continue conversations
- DO NOT add examples unless asked
- DO NOT roleplay or create scenarios
- DO NOT write "User:" or "Assistant:"
- If answer is unknown, say: "Not found in notes."

Keep answers VERY SHORT.
"""

loader = TextLoader("notes.txt")
documents = loader.load()

text_splitter = CharacterTextSplitter(chunk_size=300, chunk_overlap=50)
docs = text_splitter.split_documents(documents)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix SSL/TLS issue on Windows
import ssl
import os
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

db = Chroma.from_documents(docs, embeddings)

#  a smaller local Ollama model to fit the available RAM
llm = Ollama(
    model="gemma:2b",
    temperature=0.2,
    num_predict=120,
    system=system_prompt,
    stop=["User:", "Assistant:", "\nUser:", "\nAssistant:"]  
)

qa = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=db.as_retriever(search_kwargs={"k": 3}),
    chain_type="stuff",
    return_source_documents=True
)

print("Hi,lm SmartStudy! Type 'exit' to quit.\n")

while True:
    query = input("Ask: ").strip()

    if query.lower() == "exit":
        break

    if query == "":
        print("Please enter a question.\n")
        continue

    result = qa(query)

    answer = result["result"]
    sources = result.get("source_documents", [])

    if not sources:
        print("\nAnswer: This is not in the provided PDF.\n")
    else:
        print("\nAnswer:", answer.strip(), "\n")