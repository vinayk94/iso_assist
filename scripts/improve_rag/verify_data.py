# scripts/improve/verify_data.py
import os
import psycopg2
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

class DataVerifier:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    
    def verify_data(self):
        cur = self.conn.cursor()
        try:
            # Check documents, chunks and embeddings counts
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM documents) as doc_count,
                    (SELECT COUNT(*) FROM chunks) as chunk_count,
                    (SELECT COUNT(*) FROM embeddings) as embedding_count,
                    (SELECT COUNT(*) FROM chunks c 
                     LEFT JOIN embeddings e ON c.id = e.chunk_id 
                     WHERE e.id IS NULL) as chunks_without_embeddings
            """)
            
            counts = cur.fetchone()
            print("\nDatabase Status:")
            print(f"Total Documents: {counts[0]}")
            print(f"Total Chunks: {counts[1]}")
            print(f"Total Embeddings: {counts[2]}")
            print(f"Chunks without Embeddings: {counts[3]}")
            
            # Check document types
            cur.execute("""
                SELECT content_type, COUNT(*) 
                FROM documents 
                GROUP BY content_type
            """)
            
            print("\nDocument Types:")
            for type, count in cur.fetchall():
                print(f"{type}: {count}")
            
            # Sample of recent chunks with their embeddings
            cur.execute("""
                SELECT 
                    d.title,
                    c.content,
                    e.id IS NOT NULL as has_embedding
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                LEFT JOIN embeddings e ON c.id = e.chunk_id
                ORDER BY c.id DESC
                LIMIT 5
            """)
            
            print("\nRecent Chunks:")
            for title, content, has_embedding in cur.fetchall():
                print(f"\nDocument: {title}")
                print(f"Content Sample: {content[:100]}...")
                print(f"Has Embedding: {has_embedding}")
                
        finally:
            cur.close()
            self.conn.close()

if __name__ == "__main__":
    verifier = DataVerifier()
    verifier.verify_data()