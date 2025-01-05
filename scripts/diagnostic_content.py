# diagnostic_content.py
import psycopg2
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()
conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
cur = conn.cursor()

try:
    # Check content distribution
    cur.execute("""
        SELECT 
            d.content_type,
            COUNT(*) as total_docs,
            COUNT(DISTINCT c.id) as chunks,
            COUNT(DISTINCT e.id) as embeddings
        FROM documents d
        LEFT JOIN chunks c ON d.id = c.document_id
        LEFT JOIN embeddings e ON c.id = e.chunk_id
        GROUP BY d.content_type;
    """)
    
    print("\nContent Distribution:")
    for row in cur.fetchall():
        print(f"\nType: {row[0]}")
        print(f"Documents: {row[1]}")
        print(f"Chunks: {row[2]}")
        print(f"Embeddings: {row[3]}")
    
    # Check specific DER-related content
    print("\n\nDER-Related Content:")
    cur.execute("""
        SELECT 
            d.id,
            d.content_type,
            d.title,
            d.url,
            COUNT(c.id) as chunk_count
        FROM documents d
        LEFT JOIN chunks c ON d.id = c.document_id
        WHERE 
            LOWER(d.title) LIKE '%der%' 
            OR LOWER(d.title) LIKE '%resource%'
            OR LOWER(d.title) LIKE '%generation%'
        GROUP BY d.id
        ORDER BY d.content_type, d.title;
    """)
    
    for row in cur.fetchall():
        print(f"\nID: {row[0]}")
        print(f"Type: {row[1]}")
        print(f"Title: {row[2]}")
        print(f"URL: {row[3]}")
        print(f"Chunks: {row[4]}")

finally:
    cur.close()
    conn.close()