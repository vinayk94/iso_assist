# diagnostic.py
import psycopg2
from dotenv import load_dotenv
import os
import requests
import logging
from urllib.parse import quote

logging.basicConfig(level=logging.INFO)

def test_url(url: str, method='head'):
    """Test URL with both HEAD and GET requests"""
    try:
        # URL encode spaces and special characters
        encoded_url = quote(url, safe=':/')
        if method == 'head':
            response = requests.head(encoded_url, timeout=10, allow_redirects=True)
        else:
            response = requests.get(encoded_url, timeout=10)
        return {
            'url': url,
            'encoded_url': encoded_url,
            'method': method,
            'status': response.status_code,
            'redirected': response.history != [],
            'final_url': response.url if response.history else url
        }
    except Exception as e:
        return {
            'url': url,
            'encoded_url': encoded_url,
            'method': method,
            'error': str(e)
        }

def analyze_url(url: str):
    """Analyze URL accessibility with different methods"""
    head_result = test_url(url, 'head')
    get_result = test_url(url, 'get')
    
    print(f"\nAnalyzing URL: {url}")
    print("HEAD request:", head_result)
    print("GET request:", get_result)


if __name__ == "__main__":
    # Test specific problematic URLs
    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()

    try:
        # Get all URLs for a specific document
        cur.execute("""
            SELECT id, url, file_name 
            FROM documents 
            WHERE file_name LIKE '%INR%10MW%'
            OR url LIKE '%INR%10MW%'
            ORDER BY url;
        """)
        
        rows = cur.fetchall()
        print(f"\nFound {len(rows)} related documents")
        
        for doc_id, url, file_name in rows:
            print(f"\n=== Document ID: {doc_id} ===")
            print(f"File name: {file_name}")
            head_result = test_url(url, 'head')
            get_result = test_url(url, 'get')
            print(f"Original URL: {url}")
            print(f"Encoded URL: {head_result.get('encoded_url')}")
            print("HEAD status:", head_result.get('status') or head_result.get('error'))
            print("GET status:", get_result.get('status') or get_result.get('error'))

    finally:
        cur.close()
        conn.close()