import os
import logging
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv

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
            else:
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='xlrd')
            
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

def get_unprocessed_documents(conn) -> List[Dict]:
    """Get documents that haven't been chunked yet"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, file_name 
            FROM documents 
            WHERE content_type = 'document'
            AND id NOT IN (SELECT document_id FROM chunks);
        """)
        return [{"id": row[0], "file_name": row[1]} for row in cur.fetchall()]
    finally:
        cur.close()

def process_document(file_path: str) -> Optional[str]:
    """Extract content from a document file"""
    try:
        ext = file_path.split('.')[-1].lower()
        content = []

        if ext == 'docx':
            loader = UnstructuredWordDocumentLoader(file_path)
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

        elif ext == 'doc':
            logging.info(f"Skipping .doc file (unsupported): {file_path}")
            return None

        else:
            logging.warning(f"Unsupported file type: {ext}")
            return None

        return '\n\n'.join(content) if content else None

    except Exception as e:
        logging.error(f"Error processing {file_path}: {e}")
        return None

def create_chunks(content: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """Split content into chunks"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    return splitter.split_text(content)

def store_chunks(doc_id: int, chunks: List[str], conn):
    """Store chunks in database"""
    cur = conn.cursor()
    try:
        chunk_data = [(doc_id, chunk, idx) for idx, chunk in enumerate(chunks)]
        execute_batch(cur, """
            INSERT INTO chunks (document_id, content, chunk_index)
            VALUES (%s, %s, %s)
        """, chunk_data)
        conn.commit()
        logging.info(f"Stored {len(chunks)} chunks for document {doc_id}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error storing chunks for document {doc_id}: {e}")
    finally:
        cur.close()

def process_all():
    """Process all unprocessed documents"""
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    
    try:
        unprocessed = get_unprocessed_documents(conn)
        logging.info(f"Found {len(unprocessed)} unprocessed documents")

        for doc in unprocessed:
            try:
                file_path = os.path.join("data/documents", doc['file_name'])
                
                if not os.path.exists(file_path):
                    # Check in subdirectories
                    found = False
                    for root, _, files in os.walk("data/documents"):
                        if doc['file_name'] in files:
                            file_path = os.path.join(root, doc['file_name'])
                            found = True
                            break
                    
                    if not found:
                        logging.error(f"File not found: {doc['file_name']}")
                        continue

                content = process_document(file_path)
                if content:
                    chunks = create_chunks(content)
                    store_chunks(doc['id'], chunks, conn)
                    logging.info(f"Processed: {doc['file_name']}")
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