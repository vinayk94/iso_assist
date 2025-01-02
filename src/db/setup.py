import os
import psycopg2
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def init_db():
    """Initialize database with tables and indexes"""
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    if not postgres_uri:
        raise ValueError("PostgreSQL URI not found in environment variables")
    
    conn = psycopg2.connect(postgres_uri)
    cur = conn.cursor()
    
    try:
        # Enable vector extension
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Create tables
        cur.execute("""
            -- URLs for tracking scraping status
            CREATE TABLE IF NOT EXISTS urls (
                id BIGSERIAL PRIMARY KEY,
                url TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'pending',
                last_attempted TIMESTAMP,
                error_message TEXT
            );

            -- Documents table for both web and local content
            CREATE TABLE IF NOT EXISTS documents (
                id BIGSERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                content_type TEXT NOT NULL,  -- 'web' or 'document'
                file_name TEXT,              -- For local documents
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_document_url UNIQUE(url)
            );
            
            -- Chunks table
            CREATE TABLE IF NOT EXISTS chunks (
                id BIGSERIAL PRIMARY KEY,
                document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
                content TEXT NOT NULL,
                chunk_index INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Embeddings table
            CREATE TABLE IF NOT EXISTS embeddings (
                id BIGSERIAL PRIMARY KEY,
                chunk_id BIGINT REFERENCES chunks(id) ON DELETE CASCADE,
                embedding vector(1024),
                model_version TEXT DEFAULT 'jina-embeddings-v3',
                tokens_used INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_chunk_embedding UNIQUE(chunk_id)
            );
            
            -- Essential indexes
            CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
            CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
            CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS embedding_vector_idx 
                ON embeddings USING hnsw (embedding vector_cosine_ops);
        """)
        
        conn.commit()
        logging.info("Database setup completed successfully!")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Setup error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_db()