import os
import psycopg2
import requests
import logging
from dotenv import load_dotenv
from psycopg2.extras import Json
import time
from tqdm import tqdm
import numpy as np
from typing import Dict, List, Optional
import sys

def get_api_key():
    """Get API key with proper environment handling"""
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("embedding_generator.log"),
        logging.StreamHandler()
    ]
)

class EmbeddingProvider:
    """Base class for embedding providers"""
    def get_embeddings(self, texts: List[str]) -> Dict:
        raise NotImplementedError

class JinaProvider(EmbeddingProvider):
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

def resume_embedding_generation(conn, provider: EmbeddingProvider, batch_size: int = 50):
    """Resume embedding generation for unprocessed chunks"""
    cur = conn.cursor()
    
    try:
        # Get total and remaining chunks
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM chunks) as total_chunks,
                (SELECT COUNT(*) FROM chunks c
                 LEFT JOIN embeddings e ON c.id = e.chunk_id
                 WHERE e.id IS NULL) as remaining_chunks,
                COALESCE(
                    (SELECT MAX(id) FROM embeddings), 0
                ) as last_processed
        """)
        total, remaining, last_processed = cur.fetchone()
        
        if remaining == 0:
            logging.info("All chunks have been processed!")
            return
            
        logging.info(f"""
Embedding Generation Status:
- Total chunks: {total:,}
- Processed: {total - remaining:,}
- Remaining: {remaining:,}
""")
        
        confirm = input("\nContinue processing remaining chunks? (yes/no): ")
        if confirm.lower() != 'yes':
            logging.info("Operation cancelled")
            return
            
        # Process remaining chunks in batches
        progress_bar = tqdm(total=remaining, desc="Processing chunks")
        
        while True:
            # Get next batch of unprocessed chunks
            cur.execute("""
                SELECT c.id, c.content, c.document_id, d.file_name
                FROM chunks c
                LEFT JOIN documents d ON c.document_id = d.id
                LEFT JOIN embeddings e ON c.id = e.chunk_id
                WHERE e.id IS NULL
                ORDER BY c.id
                LIMIT %s
            """, (batch_size,))
            
            chunks = cur.fetchall()
            if not chunks:
                break
                
            chunk_ids = [c[0] for c in chunks]
            texts = [c[1] for c in chunks]
            
            try:
                # Generate embeddings
                result = provider.get_embeddings(texts)
                
                # Store embeddings
                for i, (chunk_id, embedding) in enumerate(zip(chunk_ids, result['embeddings'])):
                    cur.execute("""
                        INSERT INTO embeddings 
                            (chunk_id, embedding, model_version, tokens_used)
                        VALUES 
                            (%s, %s, %s, %s)
                    """, (
                        chunk_id,
                        embedding,
                        result['provider'],
                        result['tokens_used'] // len(chunks)
                    ))
                
                conn.commit()
                progress_bar.update(len(chunks))
                
            except Exception as e:
                conn.rollback()
                if "quota exceeded" in str(e):
                    logging.error("\nAPI quota exceeded. Please upgrade your plan or switch providers.")
                    break
                logging.error(f"Error processing batch: {e}")
                logging.error("Continuing with next batch...")
                time.sleep(5)
                continue
            
            # Small delay between batches
            time.sleep(1)
        
        progress_bar.close()
        
        # Final status
        cur.execute("""
            SELECT COUNT(*) 
            FROM chunks c
            LEFT JOIN embeddings e ON c.id = e.chunk_id
            WHERE e.id IS NULL
        """)
        final_remaining = cur.fetchone()[0]
        
        logging.info(f"""
Final Status:
- Successfully processed: {total - final_remaining:,} chunks
- Remaining chunks: {final_remaining:,}
""")
        
    except Exception as e:
        logging.error(f"Fatal error in embedding generation: {e}")
        raise
    finally:
        cur.close()

def main():
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    jina_api_key = get_api_key()
    
    if not postgres_uri or not jina_api_key:
        logging.error("Missing required environment variables")
        return
    
    batch_size = int(os.getenv("BATCH_SIZE", "50"))
    provider = JinaProvider(jina_api_key)
    
    conn = psycopg2.connect(postgres_uri)
    try:
        resume_embedding_generation(conn, provider, batch_size)
    finally:
        conn.close()

if __name__ == "__main__":
    main()