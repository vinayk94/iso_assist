# scripts/update_urls.py
import psycopg2
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def update_existing_urls():
    """Update URLs table with already scraped entries from documents"""
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    if not postgres_uri:
        raise ValueError("PostgreSQL URI not found in environment variables")
    
    conn = psycopg2.connect(postgres_uri)
    cur = conn.cursor()
    
    try:
        logging.info("Updating existing URLs from the documents table...")
        
        # Add existing documents to urls table
        cur.execute("""
            INSERT INTO urls (url, status, last_attempted)
            SELECT url, 
                   CASE 
                       WHEN content_type = 'web' THEN 'scraped'
                       ELSE 'downloaded'
                   END AS status,
                   created_at AS last_attempted
            FROM documents
            ON CONFLICT (url) DO NOTHING
        """)
        
        conn.commit()
        logging.info("URLs table updated successfully.")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error updating existing URLs: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    update_existing_urls()
