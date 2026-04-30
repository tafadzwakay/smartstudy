# SmartStudy AI Tutor

An intelligent, offline RAG-based study assistant that answers questions from your PDF documents.

## Features

- **Offline Operation**: Works completely offline after initial setup
- **Multi-Document Support**: Load multiple PDFs from the `data/` folder
- **Intelligent Retrieval**: Uses hybrid search (BM25 + semantic) with query rewriting
- **Source Citations**: Shows exactly where answers come from
- **Conversational Memory**: Remembers context across questions
- **Agent-Based Routing**: Intelligently decides how to answer questions

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Add Your PDFs**:
   Place your study materials in the `data/` folder.

3. **Run the Web App**:
   ```bash
   streamlit run web_app.py
   ```

4. **Open Browser**:
   The app will open at `http://localhost:8501`

## Usage

1. **First Load**: The system will automatically load and process all PDFs in the `data/` folder
2. **Ask Questions**: Type your questions in the chat interface
3. **View Sources**: Expand source citations to see excerpts and page numbers
4. **Multi-Document**: The system handles multiple PDFs and cites the correct source

## Architecture

- **Frontend**: Streamlit web interface
- **Backend**: LangChain RAG pipeline
- **Model**: Ollama Gemma 2B (local LLM)
- **Embeddings**: HuggingFace sentence-transformers
- **Vector Store**: ChromaDB
- **Retrieval**: Hybrid (BM25 + Semantic)

## Requirements

- Python 3.8+
- Ollama with Gemma 2B model
- Streamlit
- LangChain
- ChromaDB
- HuggingFace Transformers

## Offline Operation

After initial setup (downloading embeddings), the system works completely offline:
- No internet required for queries
- All processing happens locally
- Perfect for schools and offline study sessions