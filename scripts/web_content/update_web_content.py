import json
import os
import psycopg2
from bs4 import BeautifulSoup
import requests
from dotenv import load_dotenv
import logging
from typing import Dict, List
from psycopg2.extras import execute_batch

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_content_update.log"),
        logging.StreamHandler()
    ]
)

class WebContentUpdater:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    
    def get_enhanced_content(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove non-content elements
                for elem in soup.select('nav, header, footer, script, style, .nav, .header, .footer'):
                    elem.decompose()
                
                # Try different content selectors
                main_content = None
                
                # Try ERCOT specific content areas first
                for selector in ['.content-area', '#mainContent', 'main', 'article']:
                    main_content = soup.select_one(selector)
                    if main_content:
                        break
                
                if main_content:
                    content = main_content.get_text(separator='\n', strip=True)
                else:
                    # Fallback to whole page but with better cleaning
                    content = []
                    for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'li']):
                        text = p.get_text().strip()
                        if len(text) > 20:  # Skip very short snippets
                            content.append(text)
                    content = '\n\n'.join(content)
                
                # Clean up the content
                lines = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and len(line) > 20:  # Skip short lines
                        lines.append(line)
                
                return '\n\n'.join(lines)
                
            return f"Error: Status code {response.status_code}"
            
        except Exception as e:
            logging.error(f"Error processing {url}: {e}")
            return f"Error: {str(e)}"
        


    def create_chunks(self, content: str, doc_id: int) -> List[Dict]:
        """Create chunks with proper size and overlap"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", ". ", "! ", "? "]
        )
        
        chunks = []
        texts = splitter.split_text(content)
        
        for i, text in enumerate(texts):
            text = text.strip()
            if len(text) < 50:  # Skip very short chunks
                continue
            
            chunks.append({
                'document_id': doc_id,
                'content': text,
                'chunk_index': i
            })
        
        return chunks
    
    def store_chunks(self, chunks: List[Dict]) -> int:
        """Store chunks in database"""
        cur = self.conn.cursor()
        stored = 0
        
        try:
            chunk_data = [(
                chunk['document_id'],
                chunk['content'],
                chunk['chunk_index']
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

    def update_web_content(self):
        """Update web content chunks"""
        cur = self.conn.cursor()
        try:
            # Get all web documents
            cur.execute("""
                SELECT id, url 
                FROM documents 
                WHERE content_type = 'web'
            """)
            documents = cur.fetchall()
            
            total_processed = 0
            total_chunks = 0
            
            for doc_id, url in documents:
                try:
                    # Get enhanced content
                    new_content = self.get_enhanced_content(url)
                    if not new_content:
                        logging.warning(f"No content extracted from {url}")
                        continue
                    
                    # Delete existing chunks and embeddings
                    cur.execute("""
                        DELETE FROM embeddings 
                        WHERE chunk_id IN (
                            SELECT id FROM chunks WHERE document_id = %s
                        )
                    """, (doc_id,))
                    
                    cur.execute("""
                        DELETE FROM chunks 
                        WHERE document_id = %s
                    """, (doc_id,))
                    
                    # Create and store new chunks
                    chunks = self.create_chunks(new_content, doc_id)
                    stored = self.store_chunks(chunks)
                    
                    total_processed += 1
                    total_chunks += stored
                    
                    logging.info(f"Processed {url}: {stored} chunks created")
                    self.conn.commit()
                    
                except Exception as e:
                    logging.error(f"Error processing {url}: {e}")
                    self.conn.rollback()
                    continue
            
            logging.info(f"""
    Update Complete:
    - Documents processed: {total_processed}
    - New chunks created: {total_chunks}
    """)
            
        finally:
            cur.close()


def main():
    updater = WebContentUpdater()
    
    print("This will update web content and require re-running embeddings.")
    confirm = input("Continue? (yes/no): ")
    
    if confirm.lower() == 'yes':
        updater.update_web_content()
        print("\nUpdate complete. Please run the embedding generator to create new embeddings.")
    else:
        print("Operation cancelled.")

if __name__ == "__main__":
    main()