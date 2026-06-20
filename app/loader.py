from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredPowerPointLoader, UnstructuredExcelLoader, UnstructuredWordDocumentLoader
import os
from pathlib import Path

from langchain_core.documents import Document

SUBJECT_KEYWORDS = {
    'algebra': 'Mathematics',
    'geometry': 'Mathematics',
    'calculus': 'Mathematics',
    'math': 'Mathematics',
    'biology': 'Biology',
    'chemistry': 'Chemistry',
    'physics': 'Physics',
    'history': 'History',
    'geography': 'Geography',
    'english': 'English',
    'language': 'Languages',
    'shona': 'Languages',
    'economics': 'Economics',
    'accounting': 'Commerce',
    'business': 'Business Studies',
    'computer': 'Computer Science',
    'ict': 'Computer Science',
    'science': 'Science',
}

def infer_document_subject(path):
    name = os.path.basename(path).lower()
    for keyword, subject in SUBJECT_KEYWORDS.items():
        if keyword in name:
            return subject
    return 'General'


def load_documents(path):
    """Load a single document"""
    ext = os.path.splitext(path)[1].lower()
    
    try:
        if ext == '.pdf':
            loader = PyPDFLoader(path)
        elif ext == '.txt':
            loader = TextLoader(path, encoding='utf-8')
        elif ext in ['.docx', '.doc']:
            loader = Docx2txtLoader(path)
        elif ext in ['.pptx', '.ppt']:
            loader = UnstructuredPowerPointLoader(path)
        elif ext in ['.xlsx', '.xls']:
            loader = UnstructuredExcelLoader(path)
        elif ext == '.csv':
            # Simple CSV loader
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return [Document(page_content=content, metadata={
                'source_file': os.path.basename(path),
                'source_path': path,
                'subject': infer_document_subject(path)
            })]
        else:
            raise ValueError(f"Unsupported file type: {ext}")
        
        documents = loader.load()
        for doc in documents:
            doc.metadata.setdefault('source_file', os.path.basename(path))
            doc.metadata.setdefault('source_path', path)
            doc.metadata.setdefault('subject', infer_document_subject(path))
        return documents
    except Exception as e:
        print(f"Error loading {path}: {str(e)}")
        return []

def load_all_documents(data_dir="data"):
    """Load all supported documents from a directory"""
    all_docs = []
    supported_exts = ['.pdf', '.txt', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.csv', '.rtf', '.odt', '.ods', '.odp']
    
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            ext = os.path.splitext(file)[1].lower()
            
            if ext in supported_exts:
                file_path = os.path.join(data_dir, file)
                try:
                    docs = load_documents(file_path)
                    # Add source metadata to each document
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
                doc.metadata.setdefault('subject', infer_document_subject(pdf_file.name))

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
                doc.metadata.setdefault('subject', infer_document_subject(txt_file.name))

            all_documents.extend(documents)
        except Exception as e:
            print(f"  - Error loading {txt_file.name}: {str(e)}")
    
    print(f"Loaded {len(all_documents)} pages total\n")
    return all_documents