import os
from typing import Dict, List
import psycopg2
from dotenv import load_dotenv
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')





def check_downloaded_files():
    """Check if downloaded documents exist"""
    base_path = Path("./data/documents")
    
    if not base_path.exists():
        logging.error("Documents directory not found!")
        return
        
    sections = [d for d in base_path.iterdir() if d.is_dir()]
    
    logging.info("\nDownloaded Files:")
    total_files = 0
    for section in sections:
        files = list(section.glob("*.*"))
        logging.info(f"\n{section.name}:")
        logging.info(f"Found {len(files)} files")
        total_files += len(files)
        
        # Show sample files
        for file in files[:3]:  # Show first 3 files of each section
            logging.info(f"- {file.name}")
            
    logging.info(f"\nTotal files downloaded: {total_files}")

def get_unprocessed_content(self) -> List[Dict]:
    """Get content that hasn't been processed yet"""
    conn = psycopg2.connect(self.postgres_uri)
    cur = conn.cursor()
    
    try:
        # First, let's see exactly what we have
        cur.execute("""
            SELECT d.id, d.url, d.title, d.content_type 
            FROM documents d
            WHERE d.content_type = 'document'
            LIMIT 1;
        """)
        
        sample = cur.fetchone()
        if sample:
            print("Sample document:")
            print(f"URL: {sample[1]}")
            # Print constructed file path
            file_path = self.get_file_path_from_url(sample[1])
            print(f"Looking for file at: {file_path}")
        
        # Then get unprocessed items
        cur.execute("""
            SELECT d.id, d.url, d.title, d.content_type 
            FROM documents d
            WHERE d.id NOT IN (
                SELECT DISTINCT document_id FROM chunks
            )
            AND content_type = 'document'
            ORDER BY d.created_at DESC;
        """)
        
        return [{
            'id': row[0],
            'url': row[1],
            'title': row[2],
            'content_type': row[3]
        } for row in cur.fetchall()]
    finally:
        cur.close()
        conn.close()

import os

def print_file_structure():
    """Print actual file structure"""
    base_dir = "data/documents"
    for root, dirs, files in os.walk(base_dir):
        level = root.replace(base_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for f in files:
            print(f"{subindent}{f}")

def debug_file_paths(url: str):
    """Debug all possible file paths we might use"""
    # Original path from URL
    filename = os.path.basename(url)
    print(f"\nDebugging paths for {filename}:")
    
    # Method 1: Direct from URL
    path1 = os.path.join("data/documents", filename)
    print(f"Path 1: {path1}")
    print(f"Exists? {os.path.exists(path1)}")
    
    # Method 2: Using section
    parts = url.split('/')
    if 'docs' in parts:
        docs_index = parts.index('docs')
        rel_path = '/'.join(parts[docs_index+1:])
        path2 = os.path.join("data/documents", rel_path)
        print(f"Path 2: {path2}")
        print(f"Exists? {os.path.exists(path2)}")


import os
import psycopg2
from dotenv import load_dotenv

def debug_file_paths(url: str):
    """Debug all possible file paths we might use"""
    filename = os.path.basename(url)
    print(f"\nDebugging paths for {filename}:")
    
    # Method 1: Direct from URL
    path1 = os.path.join("data/documents", filename)
    print(f"Path 1: {path1}")
    print(f"Exists? {os.path.exists(path1)}")
    
    # Method 2: Using section
    parts = url.split('/')
    if 'docs' in parts:
        docs_index = parts.index('docs')
        rel_path = '/'.join(parts[docs_index+1:])
        path2 = os.path.join("data/documents", rel_path)
        print(f"Path 2: {path2}")
        print(f"Exists? {os.path.exists(path2)}")


def verify_unprocessed(conn):
    """Check for unprocessed documents and web content."""
    cur = conn.cursor()

    try:
        # Check unprocessed documents
        cur.execute("""
            SELECT id, file_name 
            FROM documents 
            WHERE content_type = 'document'
            AND id NOT IN (SELECT DISTINCT document_id FROM chunks);
        """)
        unprocessed_docs = cur.fetchall()
        logging.info(f"Unprocessed Documents: {len(unprocessed_docs)}")

        # Check unprocessed web content
        cur.execute("""
            SELECT id, url 
            FROM documents 
            WHERE content_type = 'web'
            AND id NOT IN (SELECT DISTINCT document_id FROM chunks);
        """)
        unprocessed_web = cur.fetchall()
        logging.info(f"Unprocessed Web Content: {len(unprocessed_web)}")

        return unprocessed_docs, unprocessed_web

    except Exception as e:
        logging.error(f"Error verifying unprocessed content: {e}")
        return [], []
    finally:
        cur.close()



if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    # Connect to the PostgreSQL database
    conn = psycopg2.connect(postgres_uri)
    cur = conn.cursor()
    
    try:
           # Check unprocessed documents
        cur.execute("""
            SELECT d.id, d.file_name
            FROM documents d
            WHERE d.content_type = 'document'
            AND d.id NOT IN (SELECT DISTINCT document_id FROM chunks);
        """)
        unprocessed_docs = cur.fetchall()

        # Check unprocessed web content
        cur.execute("""
            SELECT d.id, d.url
            FROM documents d
            WHERE d.content_type = 'web'
            AND d.id NOT IN (SELECT DISTINCT document_id FROM chunks);
        """)
        unprocessed_web = cur.fetchall()

        # Log results
        logging.info(f"Unprocessed Documents: {len(unprocessed_docs)}")
        logging.info(f"Unprocessed Web Content: {len(unprocessed_web)}")
        
    finally:
        cur.close()
        conn.close()


