# scripts/web_content/update_web_embeddings.py
import os
import sys
import time
from typing import Dict, List
import psycopg2
from dotenv import load_dotenv
import logging
from datetime import datetime
from psycopg2.extras import execute_batch
import requests

# Add project root to Python path
#project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#sys.path.append(project_root)


class JinaProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.name = "jina-embeddings-v3"
        self.dimensions = 1024

    def get_embeddings(self, texts: List[str], retry_count=3, retry_delay=2) -> Dict:
        url = 'https://api.jina.ai/v1/embeddings'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        
        data = {
            "model": self.name,
            "task": "text-matching",
            "dimensions": self.dimensions,
            "embedding_type": "float",
            "input": texts
        }
        
        for attempt in range(retry_count):
            try:
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 402:  # Payment Required
                    raise Exception("API quota exceeded")
                response.raise_for_status()
                result = response.json()
                
                return {
                    'embeddings': [item["embedding"] for item in result["data"]],
                    'tokens_used': result["usage"]["total_tokens"],
                    'provider': self.name
                }
            except Exception as e:
                if "quota exceeded" in str(e):
                    raise
                if attempt == retry_count - 1:
                    raise
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Attempt {attempt + 1} failed, waiting {wait_time} seconds...")
                time.sleep(wait_time)

logging.basicConfig(level=logging.INFO)


def get_api_key():
    """Get API key with proper environment handling"""
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")


class WebEmbeddingUpdater:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        self.provider = JinaProvider(get_api_key())
        
    def update_web_embeddings(self, batch_size: int = 50):
        cur = self.conn.cursor()
        try:
            # Get chunks from web documents that need embeddings
            cur.execute("""
                SELECT c.id, c.content 
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                LEFT JOIN embeddings e ON c.id = e.chunk_id
                WHERE d.content_type = 'web'
                AND e.id IS NULL
                ORDER BY c.id
            """)
            
            chunks = cur.fetchall()
            total_chunks = len(chunks)
            
            if total_chunks == 0:
                logging.info("No web content chunks need embeddings")
                return
                
            logging.info(f"Found {total_chunks} chunks needing embeddings")
            
            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i + batch_size]
                chunk_ids = [c[0] for c in batch]
                texts = [c[1] for c in batch]
                
                try:
                    # Generate embeddings
                    result = self.provider.get_embeddings(texts)
                    
                    # Store embeddings
                    embedding_data = []
                    for chunk_id, embedding in zip(chunk_ids, result['embeddings']):
                        embedding_data.append((
                            chunk_id,
                            embedding,
                            result['provider'],
                            result['tokens_used'] // len(batch)
                        ))
                    
                    execute_batch(cur, """
                        INSERT INTO embeddings 
                            (chunk_id, embedding, model_version, tokens_used)
                        VALUES (%s, %s, %s, %s)
                    """, embedding_data)
                    
                    self.conn.commit()
                    logging.info(f"Processed batch {i//batch_size + 1}, {len(batch)} chunks")
                    
                except Exception as e:
                    self.conn.rollback()
                    logging.error(f"Error processing batch: {e}")
                    raise
                    
            logging.info(f"Completed embedding generation for {total_chunks} chunks")
            
        finally:
            cur.close()
            self.conn.close()

def main():
    print("Starting web content embedding update...")
    updater = WebEmbeddingUpdater()
    updater.update_web_embeddings()
    print("Update complete!")

if __name__ == "__main__":
    main()