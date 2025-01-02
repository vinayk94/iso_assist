import os
import logging
from typing import List, Dict, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv
import win32com.client  # For .doc files
import pythoncom  # For COM threading
import xlrd  # For .xls files
import tempfile
import shutil

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("document_processor.log"),
        logging.StreamHandler()
    ]
)

class ExcelLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            if self.file_path.endswith('.xlsx'):
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='openpyxl')
            else:  # .xls files
                workbook = xlrd.open_workbook(self.file_path)
                sheets = {}
                for sheet in workbook.sheets():
                    # Convert xlrd sheet to pandas dataframe
                    data = []
                    for row in range(sheet.nrows):
                        data.append([str(sheet.cell_value(row, col)) for col in range(sheet.ncols)])
                    if data:
                        sheets[sheet.name] = pd.DataFrame(data[1:], columns=data[0])
            
            documents = []
            for sheet_name, sheet_data in sheets.items():
                text = sheet_data.to_string(index=False)
                documents.append(Document(
                    page_content=text,
                    metadata={"sheet_name": sheet_name, "source": self.file_path}
                ))
            return documents
        except Exception as e:
            logging.error(f"Error loading Excel file {self.file_path}: {e}")
            return []

class DocLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch('Word.Application')
            word.Visible = False
            
            # Convert .doc to .docx
            temp_dir = tempfile.mkdtemp()
            temp_docx = os.path.join(temp_dir, 'temp.docx')
            
            try:
                # Open and save as .docx
                doc = word.Documents.Open(self.file_path)
                doc.SaveAs2(temp_docx, FileFormat=16)  # 16 = .docx format
                doc.Close()
                
                # Use UnstructuredWordDocumentLoader for the .docx
                loader = UnstructuredWordDocumentLoader(temp_docx)
                return loader.load()
                
            finally:
                word.Quit()
                shutil.rmtree(temp_dir)
                pythoncom.CoUninitialize()
                
        except Exception as e:
            logging.error(f"Error loading .doc file {self.file_path}: {e}")
            return []

def get_unprocessed_documents(conn) -> List[Dict]:
    """Get documents that haven't been chunked yet"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.id, d.file_name 
            FROM documents d
            WHERE d.content_type = 'document'
            AND d.id NOT IN (SELECT document_id FROM chunks)
            AND d.file_name IS NOT NULL;
        """)
        return [{"id": row[0], "file_name": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()

def find_file(base_dir: str, file_name: str) -> Optional[str]:
    """Find a file in directory tree"""
    for root, _, files in os.walk(base_dir):
        if file_name in files:
            return os.path.join(root, file_name)
    return None

def process_document(file_path: str) -> Optional[str]:
    """Extract content from a document file"""
    try:
        ext = file_path.split('.')[-1].lower()
        content = []

        if ext == 'docx':
            loader = UnstructuredWordDocumentLoader(file_path)
            documents = loader.load()
            content = [doc.page_content for doc in documents]

        elif ext == 'doc':
            loader = DocLoader(file_path)
            documents = loader.load()
            content = [doc.page_content for doc in documents]

        elif ext == 'pdf':
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            content = [doc.page_content for doc in documents]

        elif ext in ['xls', 'xlsx']:
            loader = ExcelLoader(file_path)
            documents = loader.load()
            content = [doc.page_content for doc in documents]

        else:
            logging.warning(f"Unsupported file type: {ext}")
            return None

        text = '\n\n'.join(content) if content else None
        if not text or len(text.strip()) < 10:  # Basic content check
            logging.warning(f"No meaningful content extracted from {file_path}")
            return None
            
        return text

    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")
        return None

def create_chunks(content: str, doc_id: int) -> List[Dict]:
    """Create chunks with quality checks"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", ",", " ", ""]
    )
    
    chunks = []
    texts = splitter.split_text(content)
    
    for i, text in enumerate(texts):
        # Quality checks
        text = text.strip()
        if len(text) < 50:  # Skip very small chunks
            continue
            
        chunks.append({
            'document_id': doc_id,
            'content': text,
            'chunk_index': i,
            'metadata': {
                'size': len(text),
                'quality_score': len(text.split()) / (len(text) / 100)  # Words per 100 chars
            }
        })
    
    return chunks

def store_chunks(chunks: List[Dict], conn) -> Tuple[int, int]:
    """Store chunks with metadata"""
    cur = conn.cursor()
    stored = 0
    
    try:
        chunk_data = [(
            chunk['document_id'],
            chunk['content'],
            chunk['chunk_index'],
            chunk['metadata']
        ) for chunk in chunks]
        
        execute_batch(cur, """
            INSERT INTO chunks (document_id, content, chunk_index, metadata)
            VALUES (%s, %s, %s, %s)
        """, chunk_data)
        
        stored = len(chunks)
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error storing chunks: {e}")
        
    finally:
        cur.close()
        
    return stored, 0

def process_all():
    """Process all unprocessed documents"""
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    
    try:
        unprocessed = get_unprocessed_documents(conn)
        logging.info(f"Found {len(unprocessed)} unprocessed documents")
        
        for doc in unprocessed:
            try:
                file_path = find_file("data/documents", doc['file_name'])
                if not file_path:
                    logging.error(f"File not found: {doc['file_name']}")
                    continue
                
                content = process_document(file_path)
                if content:
                    chunks = create_chunks(content, doc['id'])
                    stored, skipped = store_chunks(chunks, conn)
                    logging.info(f"Processed {doc['file_name']}: {stored} chunks stored, {skipped} skipped")
                else:
                    logging.warning(f"No content extracted: {doc['file_name']}")
                    
            except Exception as e:
                logging.error(f"Error processing document {doc['file_name']}: {e}")
                continue
                
    except Exception as e:
        logging.error(f"Processing failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    process_all()