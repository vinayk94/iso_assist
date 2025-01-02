import os
import logging
from typing import List, Dict, Optional, Set
import psycopg2
from psycopg2.extras import execute_batch
from bs4 import BeautifulSoup
import aiohttp
from pypdf import PdfReader
import pandas as pd
from docx import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import asyncio
from dotenv import load_dotenv
import win32com.client  # For .doc files

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("extractor.log"),
        logging.StreamHandler()
    ]
)

def clean_filename(title: str) -> str:
    """Clean title for filename comparison"""
    return "".join(c.lower() for c in title if c.isalnum() or c in (' ', '-', '_', '.'))

class ContentExtractor:
    def __init__(self):
        load_dotenv()
        self.postgres_uri = os.getenv("POSTGRESQL_URI")
        if not self.postgres_uri:
            raise ValueError("Database URI not found in environment variables")
            
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", "!", "?"],
            chunk_size=500,
            chunk_overlap=50
        )
        
        self.base_dir = "data/documents"
        self.processed_files: Set[str] = set()

    def find_file(self, title: str, section: str) -> Optional[str]:
        """Find file in section directory with better matching"""
        try:
            # Handle special cases for sections
            if section == "Transmission/Distribution Service Providers":
                section_paths = [
                    os.path.join(self.base_dir, "Transmission", "Distribution Service Providers"),
                    os.path.join(self.base_dir, "Transmission")
                ]
            else:
                section_paths = [os.path.join(self.base_dir, section)]
            
            clean_target = clean_filename(title)
            
            # Search in all possible section paths
            for section_path in section_paths:
                if not os.path.exists(section_path):
                    continue
                    
                # Walk through directory
                for root, _, files in os.walk(section_path):
                    for file in files:
                        clean_file = clean_filename(os.path.splitext(file)[0])
                        if clean_file == clean_target:
                            full_path = os.path.join(root, file)
                            if full_path not in self.processed_files:
                                self.processed_files.add(full_path)
                                return full_path
            
            logging.error(f"File not found for title: {title} in section: {section}")
            return None
            
        except Exception as e:
            logging.error(f"Error finding file for {title}: {e}")
            return None

    def get_unprocessed_content(self) -> List[Dict]:
        """Get unprocessed documents"""
        conn = psycopg2.connect(self.postgres_uri)
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT d.id, d.url, d.title, d.content_type, d.section_name
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                WHERE d.content_type = 'document'
                AND c.id IS NULL
                ORDER BY d.created_at DESC;
            """)
            
            return [{
                'id': row[0],
                'url': row[1],
                'title': row[2],
                'content_type': row[3],
                'section': row[4]
            } for row in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

    def extract_doc_file(self, file_path: str) -> Optional[str]:
        """Extract content from .doc file using Word COM object"""
        try:
            word = win32com.client.Dispatch('Word.Application')
            word.Visible = False
            
            doc = word.Documents.Open(file_path)
            content = doc.Content.Text
            
            doc.Close()
            word.Quit()
            
            return content.strip()
        except Exception as e:
            logging.error(f"Error extracting .doc file {file_path}: {e}")
            return None

    def extract_document_content(self, file_path: str) -> Optional[str]:
        """Extract content from document"""
        try:
            if not os.path.exists(file_path):
                logging.error(f"File not found: {file_path}")
                return None
                
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.docx':
                doc = Document(file_path)
                paragraphs = []
                for paragraph in doc.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        paragraphs.append(text)
                return '\n\n'.join(paragraphs)
                
            elif ext == '.pdf':
                reader = PdfReader(file_path)
                text_content = []
                for page in reader.pages:
                    text = page.extract_text().strip()
                    if text:
                        text_content.append(text)
                return '\n\n'.join(text_content)
                
            elif ext in ['.xls', '.xlsx']:
                sheets = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
                text_content = []
                for sheet_name, df in sheets.items():
                    df = df.dropna(how='all').dropna(axis=1, how='all')
                    if not df.empty:
                        text_content.append(f"Sheet: {sheet_name}\n{df.to_string(index=False)}")
                return '\n\n'.join(text_content)
            
            elif ext == '.doc':
                return self.extract_doc_file(file_path)
                
            else:
                logging.warning(f"Unsupported file type: {ext}")
                return None
            
        except Exception as e:
            logging.error(f"Error extracting content from {file_path}: {e}")
            return None

    def create_chunks(self, content: str, document_id: int) -> List[Dict]:
        """Create chunks from content"""
        chunks = self.text_splitter.split_text(content)
        return [{
            'document_id': document_id,
            'content': chunk,
            'chunk_index': i
        } for i, chunk in enumerate(chunks)]

    def store_chunks(self, chunks: List[Dict], document_id: int) -> None:
        """Store chunks in database"""
        if not chunks:
            return
            
        conn = psycopg2.connect(self.postgres_uri)
        cur = conn.cursor()
        
        try:
            chunk_data = [(c['document_id'], c['content'], c['chunk_index']) for c in chunks]
            
            execute_batch(cur, """
                INSERT INTO chunks (document_id, content, chunk_index)
                VALUES (%s, %s, %s)
            """, chunk_data)
            
            conn.commit()
            logging.info(f"Stored {len(chunks)} chunks for document {document_id}")
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Error storing chunks for document {document_id}: {e}")
        finally:
            cur.close()
            conn.close()

    async def process_document(self, item: Dict) -> None:
        """Process a single document"""
        try:
            file_path = self.find_file(item['title'], item['section'])
            if not file_path:
                return

            content = self.extract_document_content(file_path)
            if content:
                chunks = self.create_chunks(content, item['id'])
                self.store_chunks(chunks, item['id'])
                logging.info(f"Successfully processed: {item['title']}")
            else:
                logging.warning(f"No content extracted for: {item['title']}")
                
        except Exception as e:
            logging.error(f"Failed to process {item['title']}: {e}")

    async def process_all(self):
        """Process all unprocessed documents"""
        unprocessed = self.get_unprocessed_content()
        total = len(unprocessed)
        logging.info(f"Found {total} items to process")
        
        if total == 0:
            logging.info("No items to process")
            return
        
        tasks = []
        for item in unprocessed:
            task = asyncio.create_task(self.process_document(item))
            tasks.append(task)
            
        await asyncio.gather(*tasks)
        logging.info("Processing completed")

async def main():
    try:
        extractor = ContentExtractor()
        await extractor.process_all()
    except Exception as e:
        logging.error(f"Extraction process failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())