import os
import logging
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def verify_processing(conn):
    """Verify document processing status"""
    cur = conn.cursor()
    try:
        # Check document counts
        cur.execute("""
            SELECT 
                COUNT(*) total_docs,
                COUNT(CASE WHEN id IN (SELECT document_id FROM chunks) THEN 1 END) processed_docs
            FROM documents 
            WHERE content_type = 'document';
        """)
        total, processed = cur.fetchone()
        
        logging.info(f"Document Processing Status:")
        logging.info(f"Total Documents: {total}")
        logging.info(f"Processed: {processed}")
        logging.info(f"Remaining: {total - processed}")
        
        # List unprocessed documents
        if total - processed > 0:
            cur.execute("""
                SELECT id, file_name 
                FROM documents 
                WHERE content_type = 'document'
                AND id NOT IN (SELECT document_id FROM chunks)
                ORDER BY file_name;
            """)
            
            logging.info("\nUnprocessed Documents:")
            for row in cur.fetchall():
                logging.info(f"ID: {row[0]}, File: {row[1]}")
                
        # Check chunk statistics
        cur.execute("""
            SELECT 
                COUNT(*) chunk_count,
                AVG(LENGTH(content)) avg_chunk_size,
                MIN(LENGTH(content)) min_chunk_size,
                MAX(LENGTH(content)) max_chunk_size
            FROM chunks;
        """)
        stats = cur.fetchone()
        
        logging.info("\nChunk Statistics:")
        logging.info(f"Total Chunks: {stats[0]}")
        logging.info(f"Average Chunk Size: {int(stats[1] or 0)} characters")
        logging.info(f"Min Chunk Size: {stats[2]} characters")
        logging.info(f"Max Chunk Size: {stats[3]} characters")
        
    finally:
        cur.close()

if __name__ == "__main__":
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    try:
        verify_processing(conn)
    finally:
        conn.close()