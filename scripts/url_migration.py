# url_migration.py
import os
import psycopg2
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("url_migration.log"),
        logging.StreamHandler()
    ]
)

def backup_tables():
    """Backup relevant tables to JSON files"""
    conn = get_connection()
    cur = conn.cursor()
    
    backup_dir = "backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Only backup existing columns
        cur.execute("""
            SELECT id, url, title, content_type, file_name, 
                   created_at::text
            FROM documents;
        """)
        documents = [dict(zip([desc[0] for desc in cur.description], row)) 
                    for row in cur.fetchall()]
        
        # Save to JSON file
        backup_file = os.path.join(backup_dir, f"documents_backup_{timestamp}.json")
        with open(backup_file, 'w') as f:
            json.dump(documents, f, indent=2)
        
        logging.info(f"Backed up {len(documents)} documents to {backup_file}")
        
        return backup_file
        
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def restore_from_backup(backup_file: str):
    """Restore documents table from backup if needed"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Read backup file
        with open(backup_file, 'r') as f:
            documents = json.load(f)
        
        # Restore documents - only existing columns
        for doc in documents:
            cur.execute("""
                UPDATE documents 
                SET url = %s,
                    title = %s,
                    content_type = %s,
                    file_name = %s
                WHERE id = %s;
            """, (
                doc['url'],
                doc['title'],
                doc['content_type'],
                doc['file_name'],
                doc['id']
            ))
        
        conn.commit()
        logging.info(f"Restored {len(documents)} documents from {backup_file}")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Restore failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_connection():
    """Get database connection"""
    load_dotenv()
    return psycopg2.connect(os.getenv("POSTGRESQL_URI"))

def add_local_path_column():
    """Add local_path column if it doesn't exist"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            ALTER TABLE documents 
            ADD COLUMN IF NOT EXISTS local_path TEXT,
            ADD COLUMN IF NOT EXISTS original_url TEXT;
        """)
        conn.commit()
        logging.info("Added local_path and original_url columns")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error adding columns: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def get_file_mappings() -> Dict[str, str]:
    """Get mapping of filenames to their ERCOT URLs from urls table"""
    conn = get_connection()
    cur = conn.cursor()
    mappings = {}
    try:
        # Get all URLs that were originally scraped from ERCOT
        cur.execute("""
            SELECT url, status 
            FROM urls 
            WHERE url LIKE 'https://www.ercot.com%'
            AND status IN ('downloaded', 'scraped');
        """)
        for url, _ in cur.fetchall():
            filename = url.split('/')[-1]
            if filename:  # Skip empty filenames
                mappings[filename] = url
        
        logging.info(f"Found {len(mappings)} original ERCOT URLs")
        return mappings
    finally:
        cur.close()
        conn.close()

def update_document_urls():
    """Update documents table with correct URLs and local paths"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        # First, backup current URLs
        cur.execute("""
            UPDATE documents 
            SET original_url = url 
            WHERE original_url IS NULL;
        """)
        
        # Get all documents with file:// URLs
        cur.execute("""
            SELECT id, url, file_name 
            FROM documents 
            WHERE url LIKE 'file://%';
        """)
        docs = cur.fetchall()
        
        # Get original URL mappings
        url_mappings = get_file_mappings()
        
        # Get existing ERCOT URLs to avoid duplicates
        cur.execute("""
            SELECT url 
            FROM documents 
            WHERE url LIKE 'https://www.ercot.com%';
        """)
        existing_urls = {row[0] for row in cur.fetchall()}
        
        updated = 0
        skipped = 0
        
        for doc_id, current_url, file_name in docs:
            if not file_name:
                skipped += 1
                continue
                
            # Get original ERCOT URL
            if file_name in url_mappings:
                ercot_url = url_mappings[file_name]
            else:
                # Construct probable URL
                ercot_url = f"https://www.ercot.com/services/rq/{file_name}"
                logging.warning(f"Created probable URL for {file_name}")
            
            # Check if URL already exists
            if ercot_url in existing_urls:
                # Generate a unique URL by appending a timestamp
                timestamp = datetime.now().strftime("%Y%m%d")
                ercot_url = f"{ercot_url}?v={timestamp}"
                logging.warning(f"Modified URL to avoid duplicate: {ercot_url}")
            
            # Update document
            cur.execute("""
                UPDATE documents 
                SET url = %s,
                    local_path = %s
                WHERE id = %s;
            """, (ercot_url, current_url.replace('file://', ''), doc_id))
            updated += 1
            existing_urls.add(ercot_url)
        
        conn.commit()
        logging.info(f"Updated {updated} documents, skipped {skipped}")
        
        # Verify updates
        cur.execute("""
            SELECT COUNT(*) 
            FROM documents 
            WHERE url LIKE 'file://%';
        """)
        remaining_file_urls = cur.fetchone()[0]
        logging.info(f"Remaining file:// URLs: {remaining_file_urls}")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error updating URLs: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def verify_migration():
    """Verify the migration was successful"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                COUNT(*) as total_docs,
                COUNT(local_path) as docs_with_local_path,
                COUNT(*) FILTER (WHERE url LIKE 'https://www.ercot.com%') as ercot_urls,
                COUNT(*) FILTER (WHERE url LIKE 'file://%') as file_urls
            FROM documents;
        """)
        total, with_path, ercot_urls, file_urls = cur.fetchone()
        
        logging.info(f"""
Migration Status:
----------------
Total documents: {total}
Documents with local path: {with_path}
Documents with ERCOT URLs: {ercot_urls}
Documents with file:// URLs: {file_urls}
        """)
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    try:
        print("This script will update document URLs in the database.")
        
        # Create backup first
        print("Creating backup...")
        backup_file = backup_tables()
        print(f"Backup created at: {backup_file}")
        
        # Ask for confirmation
        confirm = input("Proceed with URL migration? (yes/no): ")
        
        if confirm.lower() != 'yes':
            print("Migration cancelled.")
            exit()
        
        # Run migration
        add_local_path_column()
        update_document_urls()
        verify_migration()
        
        print("\nMigration completed. Check url_migration.log for details.")
        
    except Exception as e:
        logging.error(f"Migration failed: {e}")
        print("\nMigration failed. Check url_migration.log for details.")