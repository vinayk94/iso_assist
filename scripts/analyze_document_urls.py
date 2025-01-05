# scripts/analyze_document_urls.py
import os
import psycopg2
from dotenv import load_dotenv
import requests
import logging
from datetime import datetime

def analyze_urls():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"url_analysis_{timestamp}.txt"
    
    with open(output_file, 'w') as f:
        try:
            f.write("\nDocument URLs in database:\n")
            f.write("-" * 50 + "\n")
            
            cur.execute("""
                SELECT DISTINCT d.title, d.url, d.file_name 
                FROM documents d
                WHERE d.content_type = 'document'
                ORDER BY d.title
            """)
            
            for title, url, file_name in cur.fetchall():
                f.write(f"\nTitle: {title}\n")
                f.write(f"Current URL: {url}\n")
                f.write(f"Filename: {file_name}\n")
                
                # Test URL
                try:
                    response = requests.head(url, timeout=5)
                    f.write(f"Status: {response.status_code}\n")
                except Exception as e:
                    f.write(f"Error: {str(e)}\n")
            
            f.write("\n\nWeb pages with document links:\n")
            f.write("-" * 50 + "\n")
            
            cur.execute("""
                SELECT url 
                FROM documents 
                WHERE content_type = 'web'
                AND url LIKE '%/services/rq%'
            """)
            
            for (url,) in cur.fetchall():
                f.write(f"\nChecking: {url}\n")
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        f.write("Page accessible\n")
                    else:
                        f.write(f"Status: {response.status_code}\n")
                except Exception as e:
                    f.write(f"Error: {str(e)}\n")
                    
            print(f"Analysis saved to {output_file}")
                    
        finally:
            cur.close()
            conn.close()

def analyze_document_urls():
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()
    
    try:
        # Show all document URLs grouped by title
        cur.execute("""
            SELECT 
                title,
                COUNT(*) as count,
                array_agg(url) as urls,
                array_agg(content_type) as types
            FROM documents
            GROUP BY title
            HAVING COUNT(*) > 1
            ORDER BY count DESC;
        """)
        
        results = cur.fetchall()
        print(f"\nFound {len(results)} documents with multiple entries:")
        
        for title, count, urls, types in results:
            print(f"\nTitle: {title}")
            print(f"Count: {count}")
            for url, type in zip(urls, types):
                print(f"- [{type}] {url}")
                
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    #analyze_document_urls()
    analyze_urls()
