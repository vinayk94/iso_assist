# url_cleanup.py
import os
from typing import Optional
import psycopg2
import logging
from dotenv import load_dotenv
from urllib.parse import urlparse, urljoin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class URLHandler:
    BASE_URL = "https://www.ercot.com"
    FILE_BASE = "/files/docs/"
    SERVICE_BASE = "/services/rq/"
    
    @classmethod
    def normalize_url(cls, url: str, file_name: Optional[str] = None) -> str:
        if url.startswith('file://'):
            if file_name:
                return urljoin(cls.BASE_URL + cls.FILE_BASE, file_name)
            return url
            
        if cls.BASE_URL in url:
            parsed = urlparse(url)
            path = parsed.path
            
            if cls.FILE_BASE in path:
                return url
                
            if cls.SERVICE_BASE in path:
                return cls.BASE_URL + path.split('?')[0]
                
        return url

def cleanup_urls():
    """Clean up URLs while handling duplicates"""
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # First, identify groups of documents that would have the same normalized URL
        cur.execute("""
            WITH normalized_urls AS (
                SELECT 
                    id,
                    url,
                    file_name,
                    CASE 
                        WHEN url LIKE 'file://%' THEN 
                            CONCAT('https://www.ercot.com/files/docs/', file_name)
                        WHEN url LIKE '%?v=%' THEN 
                            SUBSTRING(url FROM 1 FOR POSITION('?' IN url) - 1)
                        ELSE url 
                    END as normalized_url
                FROM documents
            )
            SELECT 
                normalized_url,
                ARRAY_AGG(id) as doc_ids,
                ARRAY_AGG(url) as urls,
                COUNT(*) as doc_count
            FROM normalized_urls
            GROUP BY normalized_url
            HAVING COUNT(*) > 1
            ORDER BY normalized_url;
        """)
        
        duplicate_groups = cur.fetchall()
        
        # Handle each group of potential duplicates
        for norm_url, doc_ids, urls, count in duplicate_groups:
            logging.info(f"Found {count} documents that would normalize to: {norm_url}")
            
            # Keep the original URL for the first document (usually the one without version)
            primary_id = doc_ids[0]
            
            # For others, append a unique identifier
            for idx, doc_id in enumerate(doc_ids[1:], 1):
                unique_url = f"{norm_url}_v{idx}"
                cur.execute("""
                    UPDATE documents 
                    SET url = %s 
                    WHERE id = %s
                """, (unique_url, doc_id))
                logging.info(f"Updated document {doc_id} to use URL: {unique_url}")
        
        # Now handle the rest (non-duplicates)
        cur.execute("""
            SELECT id, url, file_name 
            FROM documents d1
            WHERE NOT EXISTS (
                SELECT 1 FROM documents d2
                WHERE d2.url = d1.url AND d2.id != d1.id
            )
        """)
        
        for doc_id, url, file_name in cur.fetchall():
            normalized_url = URLHandler.normalize_url(url, file_name)
            if normalized_url != url:
                cur.execute("""
                    UPDATE documents 
                    SET url = %s 
                    WHERE id = %s
                """, (normalized_url, doc_id))
                logging.info(f"Normalized URL for document {doc_id}: {normalized_url}")
        
        conn.commit()
        logging.info("URL cleanup completed successfully")
        
        # Print final statistics
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE url LIKE 'file://%') as file_urls,
                COUNT(*) FILTER (WHERE url LIKE 'https://www.ercot.com/files/docs/%') as doc_urls,
                COUNT(*) FILTER (WHERE url LIKE 'https://www.ercot.com/services/rq/%') as service_urls
            FROM documents;
        """)
        stats = cur.fetchone()
        logging.info(f"""
Final URL Statistics:
- File URLs remaining: {stats[0]}
- Document URLs: {stats[1]}
- Service URLs: {stats[2]}
""")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error during URL cleanup: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    #cleanup_urls()

    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()

    # Check URL patterns
    cur.execute("""
    SELECT id, url, file_name
    FROM documents 
    WHERE url NOT LIKE 'https://www.ercot.com/files/docs/%'
    AND url NOT LIKE 'https://www.ercot.com/services/rq/%'
    AND url NOT LIKE 'file://%';
    """)
    print(cur.fetchone())