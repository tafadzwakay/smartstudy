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

from app.loader import load_all_documents
from app.rag import split_docs, create_vector_db, build_agent_based_qa, format_sources

# Load all PDFs from data folder
print("Loading study materials...\n")
docs = load_all_documents("data")

# Split
chunks = split_docs(docs)

# Store
db = create_vector_db(chunks)

# Build agent-based QA system with hybrid retrieval
agent_executor, retriever = build_agent_based_qa(chunks, db)

print("SmartStudy Agent - Type 'exit' to quit.\n")
print("Powered by intelligent routing, query rewriting, and multi-document support.\n")

# Ask questions with agent-based routing
while True:
    query = input("Ask: ").strip()

    if query.lower() == "exit":
        print("Goodbye!")
        break

    if query == "":
        print("Please enter a question.\n")
        continue

    print("\n" + "="*60)
    print("Thinking...")
    print("="*60 + "\n")
    
    try:
        # Run the agent
        result = agent_executor.invoke({"input": query})
        answer = result.get("output", "No response generated")
        
        print("\nAnswer:", answer.strip())
        
        # Get source documents for citation
        sources = retriever.get_relevant_documents(query)
        
        if sources:
            formatted = format_sources(sources)
            print(f"\nSources ({len(formatted)} found):")
            for source in formatted:
                print(f"\n  [{source['source_number']}] {source['source_file']} - Page {source['page']}")
                print(f"      {source['excerpt']}")
        else:
            print("\nSources: Not found in the documents.")
        
        print("\n" + "="*60 + "\n")
        
    except Exception as e:
        print(f"Error: {str(e)}\n")