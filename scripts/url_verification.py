# verification.py
import os
import psycopg2
import requests
from dotenv import load_dotenv
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("verification.log"),
        logging.StreamHandler()
    ]
)

def get_connection():
    """Get database connection"""
    load_dotenv()
    return psycopg2.connect(os.getenv("POSTGRESQL_URI"))

def check_url(url: str) -> Tuple[str, bool, str]:
    """Check if a URL is accessible"""
    try:
        response = requests.head(url, timeout=10, allow_redirects=True)
        return url, response.status_code == 200, f"Status: {response.status_code}"
    except Exception as e:
        return url, False, str(e)

def verify_migration():
    """Verify the success of URL migration"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # 1. Check for any remaining file:// URLs
        cur.execute("""
            SELECT COUNT(*) 
            FROM documents 
            WHERE url LIKE 'file://%';
        """)
        file_urls_count = cur.fetchone()[0]
        
        # 2. Get statistics about URLs and paths
        cur.execute("""
            SELECT 
                COUNT(*) as total_docs,
                COUNT(local_path) as docs_with_path,
                COUNT(*) FILTER (WHERE url LIKE 'https://www.ercot.com%') as ercot_urls,
                COUNT(original_url) as docs_with_original
            FROM documents;
        """)
        total, with_path, ercot_urls, with_original = cur.fetchone()
        
        # 3. Sample some documents to verify structure
        cur.execute("""
            SELECT id, url, local_path, original_url, file_name
            FROM documents
            LIMIT 5;
        """)
        sample_docs = cur.fetchall()
        
        # 4. Get all ERCOT URLs for checking
        cur.execute("""
            SELECT id, url, file_name
            FROM documents 
            WHERE url LIKE 'https://www.ercot.com%'
            ORDER BY id;
        """)
        all_urls = cur.fetchall()
        
        # Print basic statistics
        print("\nMigration Verification Results:")
        print("-" * 50)
        print(f"Total documents: {total}")
        print(f"Documents with local paths: {with_path}")
        print(f"Documents with ERCOT URLs: {ercot_urls}")
        print(f"Documents with original URLs: {with_original}")
        print(f"Remaining file:// URLs: {file_urls_count}")
        
        # Print sample document structure
        print("\nSample Document Structure:")
        print("-" * 50)
        for doc in sample_docs:
            print(f"\nDocument ID: {doc[0]}")
            print(f"URL: {doc[1]}")
            print(f"Local Path: {doc[2]}")
            print(f"Original URL: {doc[3]}")
            print(f"File Name: {doc[4]}")
        
        # Check URL accessibility
        print("\nChecking URL Accessibility:")
        print("-" * 50)
        
        results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {
                executor.submit(check_url, url): (doc_id, url, filename) 
                for doc_id, url, filename in all_urls
            }
            
            for future in as_completed(future_to_url):
                doc_id, url, filename = future_to_url[future]
                url_result, is_accessible, status = future.result()
                results.append({
                    'doc_id': doc_id,
                    'url': url,
                    'filename': filename,
                    'accessible': is_accessible,
                    'status': status
                })
        
        # Create DataFrame for better analysis
        df = pd.DataFrame(results)
        
        print(f"\nTotal URLs checked: {len(df)}")
        print(f"Accessible URLs: {df['accessible'].sum()}")
        print(f"Inaccessible URLs: {len(df) - df['accessible'].sum()}")
        
        # Save detailed results
        df.to_csv('url_verification_results.csv', index=False)
        print("\nDetailed results saved to 'url_verification_results.csv'")
        
    finally:
        cur.close()
        conn.close()

# Check URLs for this specific document
import psycopg2
from dotenv import load_dotenv
import os



if __name__ == "__main__":
    #verify_migration()

    load_dotenv()
    conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    cur = conn.cursor()

    # Find the actual working URL for this document
    cur.execute("""
        SELECT d.id, d.url, d.file_name, d.content_type
        FROM documents d
        WHERE d.file_name LIKE '%INR%Resource%10MW%'
        OR d.url LIKE '%INR%Resource%10MW%';
    """)

    print("\nMatching documents:")
    for row in cur.fetchall():
        print(f"ID: {row[0]}")
        print(f"URL: {row[1]}")
        print(f"File name: {row[2]}")
        print(f"Content type: {row[3]}")
        print("---")

    cur.close()
    conn.close()