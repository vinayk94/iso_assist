# scripts/reprocess_chunks.py
import os
from typing import List, Dict, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from langchain_community.document_loaders import UnstructuredWordDocumentLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from dotenv import load_dotenv
import win32com.client
import pythoncom
import xlrd
import tempfile
import shutil
import logging
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup


# src/utils/url_handler.py

from urllib.parse import urlparse, quote, urljoin
from typing import Optional


class DocLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch('Word.Application')
            word.Visible = False
            
            temp_dir = tempfile.mkdtemp()
            temp_docx = os.path.join(temp_dir, 'temp.docx')
            
            try:
                doc = word.Documents.Open(self.file_path)
                doc.SaveAs2(temp_docx, FileFormat=16)
                doc.Close()
                
                loader = UnstructuredWordDocumentLoader(temp_docx)
                return loader.load()
            finally:
                word.Quit()
                shutil.rmtree(temp_dir)
                pythoncom.CoUninitialize()
        except Exception as e:
            logging.error(f"Error loading .doc file {self.file_path}: {e}")
            return []

class URLHandler:
    """Handle URL management for ERCOT documents"""
    
    BASE_URL = "https://www.ercot.com"
    FILE_BASE = "/files/docs/"
    SERVICE_BASE = "/services/rq/"
    
    @classmethod
    def normalize_url(cls, url: str, file_name: Optional[str] = None) -> str:
        """Normalize URLs to standard ERCOT format"""
        if not url:
            return url
            
        # Remove version suffixes and clean spaces
        url = url.split('_v')[0]  # Remove _v1, _v2 etc.
        
        if url.startswith('file://'):
            # Convert file URL to ERCOT URL format
            if file_name:
                # Look up the original URL from the documents table
                return cls._get_original_url(file_name)
            return url
            
        if cls.BASE_URL in url:
            # Already an ERCOT URL
            parsed = urlparse(url)
            path = parsed.path
            
            # Remove any query parameters or versioning
            path = path.split('?')[0].split('_v')[0]
            
            # Check if it's a document URL
            if path.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
                # Ensure proper encoding of spaces and special characters
                filename = path.split('/')[-1]
                encoded_filename = quote(filename)
                base_path = '/'.join(path.split('/')[:-1])
                path = f"{base_path}/{encoded_filename}"
                
                # Ensure document URLs use /files/docs/
                if cls.SERVICE_BASE in path:
                    path = path.replace(cls.SERVICE_BASE, cls.FILE_BASE)
                
            return cls.BASE_URL + path
                
        return url

    @classmethod
    def _get_original_url(cls, file_name: str) -> str:
        """Get original ERCOT URL from filename"""
        # Look up the URL from your documents table
        # For now, construct a probable URL
        encoded_name = quote(file_name)
        return f"{cls.BASE_URL}{cls.FILE_BASE}{encoded_name}"

    @classmethod
    def get_document_url(cls, file_name: str, content_type: str) -> str:
        """Generate proper ERCOT URL for a document"""
        encoded_name = quote(file_name)
        if content_type == 'web':
            return urljoin(cls.BASE_URL + cls.SERVICE_BASE, encoded_name)
        else:
            return urljoin(cls.BASE_URL + cls.FILE_BASE, encoded_name)
        
class ExcelLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        try:
            if self.file_path.endswith('.xlsx'):
                sheets = pd.read_excel(self.file_path, sheet_name=None, engine='openpyxl')
            else:
                workbook = xlrd.open_workbook(self.file_path)
                sheets = {}
                for sheet in workbook.sheets():
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

        
class DocumentLoader:
    """Base class for document loaders"""
    @staticmethod
    def get_loader(file_path: str):
        ext = file_path.split('.')[-1].lower()
        if ext == 'docx':
            return UnstructuredWordDocumentLoader(file_path)
        elif ext == 'doc':
            return DocLoader(file_path)
        elif ext == 'pdf':
            return PyPDFLoader(file_path)
        elif ext in ['xls', 'xlsx']:
            return ExcelLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")


class DocumentProcessor:
    def __init__(self):
        self.url_handler = URLHandler()
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))

    def register_documents(self, directory: str):
        """Register documents with proper URL handling"""
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT file_name, url FROM documents WHERE content_type = 'document'")
            existing_files = {row[0]: row[1] for row in cur.fetchall()}
            
            for root, _, files in os.walk(directory):
                for file in files:
                    if file in existing_files:
                        continue
                    
                    abs_path = os.path.abspath(os.path.join(root, file))
                    url = self.url_handler.get_document_url(file, 'document')
                    
                    cur.execute("""
                        INSERT INTO documents 
                            (url, title, content_type, file_name, local_path)
                        VALUES (%s, %s, 'document', %s, %s)
                        ON CONFLICT (url) DO UPDATE 
                        SET local_path = EXCLUDED.local_path
                    """, (url, file, file, abs_path))
            
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cur.close()

    def process_document(self, file_path: str) -> Optional[str]:
        """Process a single document"""
        try:
            loader = DocumentLoader.get_loader(file_path)
            documents = loader.load()
            if not documents:
                return None
            
            return '\n\n'.join(doc.page_content for doc in documents)
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")
            return None

    def create_chunks(self, content: str, doc_id: int) -> List[Dict]:
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
            text = text.strip()
            if len(text) < 50:
                continue
                
            chunks.append({
                'document_id': doc_id,
                'content': text,
                'chunk_index': i,
                'metadata': {
                    'size': len(text),
                    'quality_score': len(text.split()) / (len(text) / 100)
                }
            })
        
        return chunks

    def store_chunks(self, chunks: List[Dict]) -> Tuple[int, int]:
        """Store chunks with metadata"""
        cur = self.conn.cursor()
        stored = 0
        
        try:
            chunk_data = [(
                chunk['document_id'],
                chunk['content'],
                chunk['chunk_index']
                # Removed metadata as it's not in our schema
            ) for chunk in chunks]
            
            execute_batch(cur, """
                INSERT INTO chunks (document_id, content, chunk_index)
                VALUES (%s, %s, %s)
            """, chunk_data)
            
            stored = len(chunks)
            self.conn.commit()
            
        except Exception as e:
            self.conn.rollback()
            logging.error(f"Error storing chunks: {e}")
            
        finally:
            cur.close()
            
        return stored

    def process_web_content(self, url: str) -> Optional[str]:
        """Process web content"""
        try:
            import requests
            from bs4 import BeautifulSoup
            
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove scripts and styles
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Extract text
                text = soup.get_text(separator='\n', strip=True)
                return text
            else:
                logging.error(f"Failed to fetch {url}: Status {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Error processing web content {url}: {e}")
            return None

    def process_all(self, directory: str):
        """Process all documents and web content"""
        try:
            # First register any new documents
            self.register_documents(directory)
            
            # Get unprocessed documents and web content
            cur = self.conn.cursor()
            cur.execute("""
                SELECT id, file_name, url, content_type 
                FROM documents 
                WHERE id NOT IN (SELECT document_id FROM chunks)
                AND (
                    (content_type = 'document' AND file_name IS NOT NULL)
                    OR content_type = 'web'
                );
            """)
            unprocessed = cur.fetchall()
            
            logging.info(f"Found {len(unprocessed)} unprocessed items")
            
            for doc_id, file_name, url, content_type in unprocessed:
                try:
                    content = None
                    
                    if content_type == 'document':
                        # Process document
                        file_path = None
                        for root, _, files in os.walk(directory):
                            if file_name in files:
                                file_path = os.path.join(root, file_name)
                                break
                        
                        if not file_path:
                            logging.error(f"File not found: {file_name}")
                            continue
                        
                        content = self.process_document(file_path)
                        if content:
                            chunks = self.create_chunks(content, doc_id)
                            stored, skipped = self.store_chunks(chunks)
                            logging.info(f"Processed document {file_name}: {stored} chunks stored, {skipped} skipped")
                        else:
                            logging.warning(f"No content extracted from document: {file_name}")
                    
                    else:  # web content
                        # Process web content
                        content = self.process_web_content(url)
                        if content:
                            chunks = self.create_chunks(content, doc_id)
                            stored, skipped = self.store_chunks(chunks)
                            logging.info(f"Processed web content {url}: {stored} chunks stored, {skipped} skipped")
                        else:
                            logging.warning(f"No content extracted from web: {url}")
                    
                except Exception as e:
                    logging.error(f"Error processing document {file_name}: {e}")
                    continue
                    
        finally:
            self.conn.close()

logging.basicConfig(level=logging.INFO)

def reprocess_chunks():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT d.id, d.title, d.url 
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            WHERE d.url LIKE '%/files/docs/%'
            GROUP BY d.id, d.title, d.url
            HAVING COUNT(c.id) = 0
        """)
        
        docs = cur.fetchall()
        print(f"\nFound {len(docs)} documents to process:")
        
        processor = DocumentProcessor()
        for doc_id, title, url in docs:
            print(f"\nProcessing: {title}")
            
            try:
                # Get file extension from URL
                file_ext = url.split('.')[-1].lower()
                
                # Download and process document
                response = requests.get(url)
                if response.status_code == 200:
                    # Create temp file with correct extension
                    with tempfile.NamedTemporaryFile(suffix=f'.{file_ext}', delete=False) as temp_file:
                        temp_file.write(response.content)
                        temp_path = temp_file.name
                    
                    try:
                        # Process document
                        content = processor.process_document(temp_path)
                        if content:
                            # Create chunks
                            chunks = processor.create_chunks(content, doc_id)
                            stored = processor.store_chunks(chunks)  # Changed here
                            print(f"Created {stored} chunks")
                        else:
                            print(f"No content extracted from {title}")
                    finally:
                        # Clean up temp file
                        os.unlink(temp_path)
                else:
                    print(f"Failed to download {title}: Status {response.status_code}")
                    
            except Exception as e:
                print(f"Error processing {title}: {e}")
                continue
        
        conn.commit()
        print("\nProcessing complete!")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    reprocess_chunks()

