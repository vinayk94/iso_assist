import os
import logging
import sys
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


# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)



# test_search.py
from src.assistant.rag_assistant import ERCOTRAGAssistant
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def test_search():
    assistant = ERCOTRAGAssistant()
    try:
        # Test vector search
        print("\nTesting vector search...")
        chunks = await assistant.vector_search("How to register DER?")
        print(f"\nFound {len(chunks)} chunks")
        
        for chunk in chunks:
            print("\n---")
            print(f"Title: {chunk['metadata']['title']}")
            print(f"URL: {chunk['metadata']['url']}")
            print(f"Content type: {chunk['metadata']['type']}")
            print("First 100 chars:", chunk['content'][:100])
        
        # Test full query
        print("\nTesting full query...")
        result = await assistant.process_query("How to register DER?")
        
        print("\nAnswer:", result['answer'])
        print("\nSources used:")
        for source in result['sources']:
            print(f"\n- {source['metadata']['title']}")
            print(f"  URL: {source['metadata']['url']}")
            
    except Exception as e:
        logging.error(f"Test error: {str(e)}", exc_info=True)
    finally:
        if hasattr(assistant, 'conn'):
            assistant.conn.close()

if __name__ == "__main__":
    asyncio.run(test_search())

        