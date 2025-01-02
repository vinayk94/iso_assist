import os
import logging
import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv
from typing import List, Dict
import pandas as pd

from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("processor.log"),
        logging.StreamHandler()
    ]
)


class ExcelLoader:
    """Loader for Excel files."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Dict]:
        """Load Excel file and parse content."""
        documents = []
        try:
            if self.file_path.endswith('.xlsx'):
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='openpyxl')
            else:
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='xlrd')

            for sheet_name, data in sheets.items():
                text = data.to_string(index=False)
                documents.append({
                    "page_content": text,
                    "metadata": {"sheet_name": sheet_name, "source": self.file_path}
                })
        except Exception as e:
            logging.error(f"Failed to load Excel file {self.file_path}: {e}")
        return documents


def chunk_text(data: List[Dict], chunk_size: int = 500, chunk_overlap: int = 50) -> List[Dict]:
    """Chunk content into smaller pieces."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
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
    """Store processed chunks in the database."""
    cur = conn.cursor()
    try:
        chunk_data = [(chunk["metadata"]["id"], chunk["content"], chunk["chunk_index"]) for chunk in chunks]
        execute_batch(cur, """
            INSERT INTO chunks (document_id, content, chunk_index)
            VALUES (%s, %s, %s)
        """, chunk_data)
        conn.commit()
        logging.info(f"Stored {len(chunk_data)} chunks successfully.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Failed to store chunks: {e}")
    finally:
        cur.close()


def reprocess_documents(unprocessed_docs, directory, conn):
    """Reprocess unprocessed documents."""
    missing_files = set()
    processed_count = 0

    for doc_id, file_name in unprocessed_docs:
        if not file_name:
            logging.warning(f"Skipping document with ID {doc_id}: missing file_name")
            continue

        file_path = os.path.join(directory, file_name)
        if not os.path.exists(file_path):
            if file_path not in missing_files:
                missing_files.add(file_path)
                logging.warning(f"File not found for document ID {doc_id}: {file_name}")
            continue

        try:
            loader = None
            ext = file_name.split('.')[-1].lower()
            if ext == 'docx':
                loader = UnstructuredWordDocumentLoader(file_path)
            elif ext == 'pdf':
                loader = PyPDFLoader(file_path)
            elif ext in ['xls', 'xlsx']:
                loader = ExcelLoader(file_path)
            else:
                logging.warning(f"Unsupported file type for document ID {doc_id}: {file_name}")
                continue

            documents = loader.load()
            processed_data = [
                {"content": doc["page_content"], "metadata": {"id": doc_id, "file_name": file_name}}
                for doc in documents
            ]

            if processed_data:
                chunks = chunk_text(processed_data)
                store_chunks(chunks, conn)
                processed_count += 1
                logging.info(f"Processed document ID {doc_id}: {file_name}")
        except Exception as e:
            logging.error(f"Failed to process document ID {doc_id}: {e}")

    logging.info(f"Reprocessed {processed_count} documents.")


def reprocess_web_content(unprocessed_web, conn):
    """Reprocess unprocessed web content."""
    processed_count = 0

    for doc_id, url in unprocessed_web:
        if not url:
            logging.warning(f"Skipping web content with ID {doc_id}: missing URL")
            continue

        try:
            # Simulate content retrieval
            content = f"Processed content from {url}"
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO chunks (document_id, content, chunk_index)
                VALUES (%s, %s, %s)
            """, (doc_id, content, 0))
            conn.commit()
            processed_count += 1
            logging.info(f"Processed web content ID {doc_id}: {url}")
        except Exception as e:
            logging.error(f"Failed to process web content ID {doc_id}: {e}")

    logging.info(f"Reprocessed {processed_count} web content entries.")


def verify_unprocessed(conn):
    """Verify unprocessed documents and web content."""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, file_name 
            FROM documents 
            WHERE content_type = 'document'
            AND id NOT IN (SELECT document_id FROM chunks);
        """)
        unprocessed_docs = cur.fetchall()

        cur.execute("""
            SELECT id, url 
            FROM documents 
            WHERE content_type = 'web'
            AND id NOT IN (SELECT document_id FROM chunks);
        """)
        unprocessed_web = cur.fetchall()

        logging.info(f"Unprocessed Documents: {len(unprocessed_docs)}")
        logging.info(f"Unprocessed Web Content: {len(unprocessed_web)}")
        return unprocessed_docs, unprocessed_web
    finally:
        cur.close()


def reprocess_all_unprocessed_content(directory, conn):
    """Reprocess all unprocessed content."""
    unprocessed_docs, unprocessed_web = verify_unprocessed(conn)

    if unprocessed_docs:
        logging.info("Reprocessing unprocessed documents...")
        reprocess_documents(unprocessed_docs, directory, conn)
    else:
        logging.info("No unprocessed documents found.")

    if unprocessed_web:
        logging.info("Reprocessing unprocessed web content...")
        reprocess_web_content(unprocessed_web, conn)
    else:
        logging.info("No unprocessed web content found.")




import psycopg2
import logging
from dotenv import load_dotenv
import os

def analyze_missing_entries(conn):
    """Analyze missing entries by content_type and report the counts."""
    try:
        cur = conn.cursor()

        # Query to get missing file names for documents
        cur.execute("""
            SELECT id, file_name, content_type
            FROM documents
            WHERE 
                (file_name IS NULL OR file_name = '')
                OR (content_type = 'document' AND id NOT IN (SELECT DISTINCT document_id FROM chunks));
        """)
        missing_entries = cur.fetchall()

        # Group the results by content_type
        missing_documents = [entry for entry in missing_entries if entry[2] == 'document']
        missing_web_content = [entry for entry in missing_entries if entry[2] == 'web']

        logging.info(f"Total Missing Entries: {len(missing_entries)}")
        logging.info(f"Missing Documents: {len(missing_documents)}")
        logging.info(f"Missing Web Content: {len(missing_web_content)}")

        # Print details of missing documents and web content
        if missing_documents:
            logging.info("Missing Documents Details:")
            for doc in missing_documents:
                logging.info(f"ID: {doc[0]}, File Name: {doc[1]}")
        else:
            logging.info("No missing documents.")

        if missing_web_content:
            logging.info("Missing Web Content Details:")
            for web in missing_web_content:
                logging.info(f"ID: {web[0]}, URL: {web[1]}")
        else:
            logging.info("No missing web content.")

    except Exception as e:
        logging.error(f"Error analyzing missing entries: {e}")
    finally:
        cur.close()

if __name__ == "__main__":
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")

    if not postgres_uri:
        raise ValueError("POSTGRESQL_URI not found in environment")

    try:
        conn = psycopg2.connect(postgres_uri)
        verify_unprocessed(conn)
    except Exception as e:
        logging.error(f"Error during analysis: {e}")
    finally:
        conn.close()


