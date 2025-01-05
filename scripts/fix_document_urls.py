# scripts/fix_document_urls.py
import os
import psycopg2
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

def fix_document_urls():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # Find documents to delete (404 URLs)
        cur.execute("""
            SELECT id, title, url 
            FROM documents
            WHERE content_type = 'document'
            AND url LIKE '%/services/rq/%'
        """)
        
        to_delete = cur.fetchall()
        if not to_delete:
            print("No documents to clean up")
            return
            
        print(f"\nFound {len(to_delete)} documents to remove:")
        for id, title, url in to_delete:
            print(f"- [{id}] {title}")
            print(f"  URL: {url}")
            
        confirm = input("\nRemove these documents? (yes/no): ")
        
        if confirm.lower() == 'yes':
            ids_to_delete = [doc[0] for doc in to_delete]
            
            # Delete in correct order
            cur.execute("DELETE FROM embeddings WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = ANY(%s))", (ids_to_delete,))
            cur.execute("DELETE FROM chunks WHERE document_id = ANY(%s)", (ids_to_delete,))
            cur.execute("DELETE FROM documents WHERE id = ANY(%s)", (ids_to_delete,))
            
            conn.commit()
            print(f"Successfully removed {len(ids_to_delete)} documents")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_document_urls()