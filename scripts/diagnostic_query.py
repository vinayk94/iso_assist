# diagnostic_query.py
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
cur = conn.cursor()

try:
    # 1. Check if embeddings are working properly
    print("\nChecking embedding connections:")
    cur.execute("""
        SELECT 
            d.content_type,
            COUNT(DISTINCT d.id) as total_docs,
            COUNT(DISTINCT c.id) as chunks_with_embeddings
        FROM documents d
        JOIN chunks c ON d.id = c.document_id
        JOIN embeddings e ON c.id = e.chunk_id
        GROUP BY d.content_type;
    """)
    for row in cur.fetchall():
        print(f"{row[0]}: {row[1]} docs, {row[2]} chunks with embeddings")

    # 2. Check DER-related content in both web and documents
    print("\nChecking DER-related content:")
    cur.execute("""
        SELECT 
            d.content_type,
            d.title,
            d.url,
            COUNT(c.id) as chunk_count,
            COUNT(e.id) as embedding_count,
            c.content as sample_content
        FROM documents d
        LEFT JOIN chunks c ON d.id = c.document_id
        LEFT JOIN embeddings e ON c.id = e.chunk_id
        WHERE 
            LOWER(d.title) LIKE '%der%' 
            OR LOWER(d.title) LIKE '%distributed%'
            OR LOWER(d.title) LIKE '%generation%'
            OR LOWER(d.title) LIKE '%resource%'
            OR d.url LIKE '%/re/%'
            OR d.url LIKE '%/integration%'
        GROUP BY d.content_type, d.title, d.url, c.content
        ORDER BY d.content_type, chunk_count DESC;
    """)
    
    for row in cur.fetchall():
        print(f"\n{row[0]}: {row[1]}")
        print(f"URL: {row[2]}")
        print(f"Chunks: {row[3]}, Embeddings: {row[4]}")
        if row[5]:
            print(f"Sample content: {row[5][:100]}...")

finally:
    cur.close()
    conn.close()