import os
import psycopg2
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# cleanup_schema.py
def cleanup_schema():
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    conn = psycopg2.connect(postgres_uri)
    cur = conn.cursor()
    
    try:
        # Remove the unnecessary section_name column
        logging.info("Removing unnecessary section_name column...")
        cur.execute("""
            ALTER TABLE documents 
            DROP COLUMN IF EXISTS section_name;
        """)

        logging.info("Updating table...")
        cur.execute("""
            ALTER TABLE documents ADD COLUMN file_name TEXT;
        """)
        
        conn.commit()
        logging.info("Schema cleanup completed!")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error cleaning schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

def update_schema():
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    conn = psycopg2.connect(postgres_uri)
    cur = conn.cursor()

    
    
    try:
        # Add section_name column
        logging.info("Adding section_name column...")
        cur.execute("""
            ALTER TABLE documents 
            ADD COLUMN IF NOT EXISTS section_name TEXT;
        """)
        
        # Update sections based on title patterns
        logging.info("Updating document sections...")
        cur.execute("""
            UPDATE documents 
            SET section_name = 
                CASE 
                    -- Credit section
                    WHEN title ILIKE '%credit%' 
                         OR title ILIKE '%surety%'
                         OR title LIKE '%DAM Proxy%'
                         OR title LIKE '%Letter of Credit%'
                        THEN 'Credit'
                    
                    -- Load Serving Entities section
                    WHEN title ILIKE '%LSE%' 
                         OR title ILIKE '%NOIE%' 
                         OR title ILIKE '%ELSE%'
                        THEN 'Load Serving Entities'
                    
                    -- Qualified Scheduling Entities section
                    WHEN title ILIKE '%QSE%' 
                         OR title LIKE '%Declaration of Subordinate%'
                         OR title = 'Market Guide'
                         OR title LIKE '%ICCP%'
                        THEN 'Qualified Scheduling Entities'
                    
                    -- Transmission/Distribution Service Providers section
                    WHEN title ILIKE '%TDSP%' 
                         OR title ILIKE '%TSP%' 
                         OR title ILIKE '%Transmission%' 
                         OR title ILIKE '%Settlement%'
                        THEN 'Transmission/Distribution Service Providers'
                    
                    -- Resource Entities section
                    WHEN title LIKE '%Resource Entities%'
                         OR title LIKE '%RE Model%'
                         OR title LIKE '%Network Model%'
                        THEN 'Resource Entities'
                    
                    -- Resource Integration section (default for remaining technical docs)
                    ELSE 'Resource Integration'
                END
            WHERE content_type = 'document';
        """)
        
        conn.commit()
        logging.info("Schema update completed successfully!")
        
        # Show section distribution
        cur.execute("""
            SELECT section_name, COUNT(*) 
            FROM documents 
            WHERE content_type = 'document'
            GROUP BY section_name
            ORDER BY COUNT(*) DESC;
        """)
        
        logging.info("\nDocument distribution by section:")
        for row in cur.fetchall():
            logging.info(f"{row[0]}: {row[1]} documents")
            
        # Show sample documents in each section
        cur.execute("""
            WITH RankedDocs AS (
                SELECT 
                    section_name,
                    title,
                    ROW_NUMBER() OVER (PARTITION BY section_name ORDER BY title) as rn
                FROM documents
                WHERE content_type = 'document'
            )
            SELECT 
                section_name,
                string_agg(title, '; ' ORDER BY title)
            FROM RankedDocs
            WHERE rn <= 3
            GROUP BY section_name;
        """)
        
        logging.info("\nSample documents in each section:")
        for row in cur.fetchall():
            logging.info(f"{row[0]}:")
            logging.info(f"  {row[1]}")
            
    except Exception as e:
        conn.rollback()
        logging.error(f"Error updating schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    cleanup_schema()