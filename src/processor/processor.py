import os
import logging
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from dotenv import load_dotenv
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from typing import List, Dict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("processor.log"),
        logging.StreamHandler()
    ]
)

class ExcelLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Dict]:
        """Load and parse Excel file into document-like objects."""
        documents = []
        try:
            logging.debug(f"Loading Excel file: {self.file_path}")
            if self.file_path.endswith('.xlsx'):
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='openpyxl')
            else:
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='xlrd')

            for sheet_name, sheet_data in sheets.items():
                text = sheet_data.to_string(index=False)
                documents.append({
                    "page_content": text,
                    "metadata": {"sheet_name": sheet_name, "source": self.file_path}
                })
        except Exception as e:
            logging.error(f"Error loading Excel file {self.file_path}: {e}")
        return documents

def register_documents(directory: str, conn):
    """Register local documents in the database."""
    cur = conn.cursor()
    registered = 0
    try:
        # Fetch existing files to avoid duplicates
        cur.execute("SELECT file_name FROM documents WHERE content_type = 'document'")
        existing_files = {row[0] for row in cur.fetchall()}

        for root, _, files in os.walk(directory):
            for file in files:
                if file in existing_files:
                    logging.info(f"Skipping already registered file: {file}")
                    continue

                # Create document URL and ensure consistent file_name registration
                abs_path = os.path.abspath(os.path.join(root, file))
                file_name = os.path.basename(abs_path)
                url = f"file://{abs_path.replace(os.sep, '/')}"

                cur.execute("""
                    INSERT INTO documents (url, title, content_type, file_name)
                    VALUES (%s, %s, 'document', %s)
                    ON CONFLICT (url) DO NOTHING
                """, (url, file_name, file_name))

                registered += 1

        conn.commit()
        logging.info(f"Registered {registered} new documents")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error registering documents: {e}")
        raise
    finally:
        cur.close()

def process_documents_in_batches(directory: str, conn, batch_size: int = 10):
    """Process document files in batches."""
    cur = conn.cursor()
    try:
        missing_files = set()  # Track files already flagged as missing
        skipped_ids = set()  # Track skipped document IDs

        while True:
            cur.execute("""
                SELECT id, file_name 
                FROM documents 
                WHERE content_type = 'document'
                AND id NOT IN (SELECT document_id FROM chunks)
                AND id NOT IN %s
                LIMIT %s
            """, (tuple(skipped_ids) or (0,), batch_size))
            documents = cur.fetchall()

            if not documents:
                logging.info("No unprocessed documents found.")
                break

            processed_count = 0
            for doc_id, file_name in documents:
                if not file_name:
                    logging.warning(f"Skipping document with ID {doc_id}: missing file_name")
                    skipped_ids.add(doc_id)
                    continue

                file_path = os.path.join(directory, file_name)
                if file_path in missing_files or not os.path.exists(file_path):
                    missing_files.add(file_path)
                    logging.warning(f"File not found for document ID {doc_id}: {file_name}")
                    skipped_ids.add(doc_id)
                    continue

                try:
                    ext = file_name.split('.')[-1].lower()
                    if ext == 'docx':
                        loader = UnstructuredWordDocumentLoader(file_path)
                    elif ext == 'pdf':
                        loader = PyPDFLoader(file_path)
                    elif ext in ['xls', 'xlsx']:
                        loader = ExcelLoader(file_path)
                    else:
                        logging.warning(f"Unsupported file type for document ID {doc_id}: {file_name}")
                        skipped_ids.add(doc_id)
                        continue

                    documents = loader.load()
                    processed_data = []
                    for doc in documents:
                        processed_data.append({
                            "content": doc["page_content"],
                            "metadata": {
                                "id": doc_id,
                                "file_name": file_name
                            }
                        })
                    logging.info(f"Processed {file_name}")
                    processed_count += 1

                    if processed_data:
                        chunks = chunk_text(processed_data)
                        store_chunks(chunks, conn)

                except Exception as e:
                    logging.error(f"Failed to process {file_name}: {e}")
                    skipped_ids.add(doc_id)

            if processed_count == 0:
                logging.info("All remaining documents in this batch are either missing or unsupported.")
                break

    finally:
        cur.close()



def chunk_text(data: List[Dict], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Dict]:
    """Create chunks from content."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunked_data = []

    for doc in data:
        chunks = splitter.split_text(doc["content"])
        for i, chunk in enumerate(chunks):
            chunked_data.append({
                "content": chunk,
                "chunk_index": i,
                "metadata": doc["metadata"]
            })

    return chunked_data

def store_chunks(chunks: List[Dict], conn):
    """Store chunks in the database."""
    cur = conn.cursor()
    try:
        chunk_data = [
            (chunk["metadata"]["id"], chunk["content"], chunk["chunk_index"])
            for chunk in chunks
        ]
        execute_batch(cur, """
            INSERT INTO chunks (document_id, content, chunk_index)
            VALUES (%s, %s, %s)
        """, chunk_data)

        conn.commit()
        logging.info(f"Stored {len(chunk_data)} chunks")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error storing chunks: {e}")
        raise
    finally:
        cur.close()

def process_web_content(conn):
    """Process web content entries."""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, url 
            FROM documents 
            WHERE content_type = 'web'
            AND id NOT IN (SELECT document_id FROM chunks)
        """)
        web_documents = cur.fetchall()

        for doc_id, url in web_documents:
            # Logic to fetch and process web content
            logging.info(f"Processing web content: {url}")

    finally:
        cur.close()

def process_all_content():
    """Complete processing pipeline."""
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")

    if not postgres_uri:
        raise ValueError("POSTGRESQL_URI not found in environment")

    try:
        conn = psycopg2.connect(postgres_uri)

        # Step 1: Register documents
        logging.info("Registering documents...")
        register_documents("data/documents", conn)

        # Step 2: Process documents in batches
        logging.info("Processing documents...")
        process_documents_in_batches("data/documents", conn, batch_size=10)

        # Step 3: Process web content
        logging.info("Processing web content...")
        process_web_content(conn)

    except Exception as e:
        logging.error(f"Processing failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    process_all_content()
