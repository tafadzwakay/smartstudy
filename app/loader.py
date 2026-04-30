from langchain_community.document_loaders import PyPDFLoader, TextLoader
import os
from pathlib import Path

def load_documents(path):
    """Load a single document (PDF or text)"""
    ext = os.path.splitext(path)[1].lower()
    
    if ext == '.pdf':
        loader = PyPDFLoader(path)
    elif ext == '.txt':
        loader = TextLoader(path, encoding='utf-8')
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    documents = loader.load()
    return documents

def load_all_documents(data_dir="data"):
    """Load all PDF and text documents from a directory"""
    all_docs = []
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            ext = os.path.splitext(file)[1].lower()
            
            if ext in ['.pdf', '.txt']:
                file_path = os.path.join(data_dir, file)
                try:
                    if ext == '.pdf':
                        loader = PyPDFLoader(file_path)
                        docs = loader.load()
                        # Add source metadata to each document
                        for doc in docs:
                            doc.metadata['source_file'] = file
                        print(f"Loaded {len(docs)} pages from {file}")
                    elif ext == '.txt':
                        loader = TextLoader(file_path, encoding='utf-8')
                        docs = loader.load()
                        for doc in docs:
                            doc.metadata['source_file'] = file
                        print(f"Loaded {len(docs)} pages from {file}")
                    all_docs.extend(docs)
                except Exception as e:
                    print(f"Error loading {file}: {str(e)}")
    
    return all_docs


def load_multiple_documents(folder_path: str):
    """
    Load all PDF and text documents from a folder.
    Automatically tags each document with its source filename.
    """
    all_documents = []
    
    # Find all supported files in the folder
    data_path = Path(folder_path)
    if not data_path.exists():
        print(f"Warning: Folder '{folder_path}' not found.")
        return all_documents
    
    pdf_files = list(data_path.glob("*.pdf"))
    txt_files = list(data_path.glob("*.txt"))
    
    if not pdf_files and not txt_files:
        print(f"Warning: No PDF or TXT files found in '{folder_path}'")
        return all_documents
    
    # Load PDFs
    for pdf_file in sorted(pdf_files):
        try:
            print(f"  - Loading: {pdf_file.name}")
            loader = PyPDFLoader(str(pdf_file))
            documents = loader.load()
            
            for doc in documents:
                doc.metadata["source_file"] = pdf_file.name
                doc.metadata["source_path"] = str(pdf_file)
            
            all_documents.extend(documents)
        except Exception as e:
            print(f"  - Error loading {pdf_file.name}: {str(e)}")
    
    # Load text files
    for txt_file in sorted(txt_files):
        try:
            print(f"  - Loading: {txt_file.name}")
            loader = TextLoader(str(txt_file), encoding='utf-8')
            documents = loader.load()
            
            for doc in documents:
                doc.metadata["source_file"] = txt_file.name
                doc.metadata["source_path"] = str(txt_file)
            
            all_documents.extend(documents)
        except Exception as e:
            print(f"  - Error loading {txt_file.name}: {str(e)}")
    
    print(f"Loaded {len(all_documents)} pages total\n")
    return all_documents