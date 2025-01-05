# debug_search.py
import os
import psycopg2
from dotenv import load_dotenv
import logging
import json

logging.basicConfig(level=logging.INFO)

def debug_db_schema():
    """Debug database schema and data"""
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # 1. Check table schema
        print("\nChecking tables schema:")
        for table in ['documents', 'chunks', 'embeddings']:
            cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}';
            """)
            print(f"\n{table} columns:")
            for col in cur.fetchall():
                print(f"- {col[0]}: {col[1]}")
        
        # 2. Check a sample query result
        print("\nChecking sample vector search query:")
        cur.execute("""
            SELECT 
                c.id as chunk_id,
                c.content,
                c.document_id,
                d.title,
                d.content_type,
                d.url,
                d.file_name,
                d.created_at,
                e.id as embedding_id
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            JOIN embeddings e ON c.id = e.chunk_id
            LIMIT 1;
        """)
        
        columns = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        
        if row:
            print("\nSample row structure:")
            for col, val in zip(columns, row):
                print(f"{col}: {val}")
        else:
            print("No results found!")
            
        # 3. Check counts
        print("\nChecking record counts:")
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM documents) as doc_count,
                (SELECT COUNT(*) FROM chunks) as chunk_count,
                (SELECT COUNT(*) FROM embeddings) as embedding_count;
        """)
        counts = cur.fetchone()
        print(f"Documents: {counts[0]}")
        print(f"Chunks: {counts[1]}")
        print(f"Embeddings: {counts[2]}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    debug_db_schema()