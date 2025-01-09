# scripts/improve/check_else_form.py
import os
import psycopg2
from dotenv import load_dotenv

def check_else_form():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # Check all versions of the ELSE form URL
        cur.execute("""
            SELECT id, title, url 
            FROM documents 
            WHERE title LIKE '%ELSE%' 
                OR url LIKE '%else%'
            ORDER BY id;
        """)
        
        results = cur.fetchall()
        print("\nELSE Form entries in database:")
        for id, title, url in results:
            print(f"\nID: {id}")
            print(f"Title: {title}")
            print(f"URL: {url}")
            
        # Check if chunks exist
        cur.execute("""
            SELECT c.id, c.content, e.id is not null as has_embedding
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            LEFT JOIN embeddings e ON c.id = e.chunk_id
            WHERE d.title LIKE '%ELSE%'
            LIMIT 5;
        """)
        
        chunks = cur.fetchall()
        print("\nChunks for ELSE form:")
        for chunk_id, content, has_embedding in chunks:
            print(f"\nChunk ID: {chunk_id}")
            print(f"Has Embedding: {has_embedding}")
            print(f"Content Preview: {content[:100]}...")
            
    finally:
        cur.close()
        conn.close()

# scripts/improve/fix_else_url.py
def fix_else_url():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # Get current URL
        cur.execute("""
            UPDATE documents 
            SET url = 'https://www.ercot.com/files/docs/2016/02/04/else_identification_and_meter_points_registration_form_ver2.xls'
            WHERE title LIKE '%ELSE%'
            RETURNING id, title, url;
        """)
        
        updated = cur.fetchone()
        if updated:
            print(f"Updated document: {updated}")
            conn.commit()
        else:
            print("No matching document found")
            
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    #check_else_form()
    fix_else_url()