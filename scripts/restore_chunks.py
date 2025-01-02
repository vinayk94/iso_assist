import psycopg2
import os
from dotenv import load_dotenv
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("restore.log"),
        logging.StreamHandler()
    ]
)

def verify_backup_exists(conn) -> bool:
    """Check if backup table exists"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables
                WHERE schemaname = 'public'
                AND tablename = 'chunks_backup'
            );
        """)
        return cur.fetchone()[0]
    finally:
        cur.close()

def count_records(conn, table: str) -> int:
    """Count records in a table"""
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
    finally:
        cur.close()

def restore_from_backup(conn):
    """Restore chunks table from backup"""
    cur = conn.cursor()
    try:
        # First verify backup exists
        if not verify_backup_exists(conn):
            logging.error("Backup table 'chunks_backup' not found!")
            return False

        # Get counts before restoration
        original_count = count_records(conn, 'chunks')
        backup_count = count_records(conn, 'chunks_backup')
        
        logging.info(f"Current chunks count: {original_count}")
        logging.info(f"Backup chunks count: {backup_count}")
        
        # Confirm restoration
        confirm = input(f"\nRestore {backup_count} chunks from backup? This will replace current {original_count} chunks. (yes/no): ")
        
        if confirm.lower() != 'yes':
            logging.info("Restoration cancelled by user")
            return False
            
        # Perform restoration
        logging.info("Starting restoration...")
        cur.execute("BEGIN;")
        
        # Delete current chunks
        cur.execute("DELETE FROM chunks;")
        logging.info("Cleared current chunks table")
        
        # Copy from backup
        cur.execute("INSERT INTO chunks SELECT * FROM chunks_backup;")
        
        # Verify counts
        new_count = count_records(conn, 'chunks')
        if new_count != backup_count:
            logging.error(f"Count mismatch after restoration! Expected {backup_count}, got {new_count}")
            cur.execute("ROLLBACK;")
            return False
            
        cur.execute("COMMIT;")
        logging.info(f"Successfully restored {new_count} chunks from backup")
        return True
        
    except Exception as e:
        cur.execute("ROLLBACK;")
        logging.error(f"Error during restoration: {e}")
        return False
    finally:
        cur.close()

def main():
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    if not postgres_uri:
        logging.error("PostgreSQL URI not found in environment variables")
        return
        
    try:
        conn = psycopg2.connect(postgres_uri)
        success = restore_from_backup(conn)
        
        if success:
            print("\nRestoration completed successfully!")
            print("You can now run the optimized chunk analyzer with improved parameters.")
        else:
            print("\nRestoration failed or was cancelled.")
            print("Please check the logs for details.")
            
    except Exception as e:
        logging.error(f"Database connection error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()