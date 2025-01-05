# scripts/improve/fix_excel_processing.py
import os
import psycopg2
from dotenv import load_dotenv
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

class ExcelProcessor:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        
    def clean_excel_content(self, content: str) -> str:
        """Clean Excel content by removing NaN and formatting properly"""
        # Replace multiple NaN occurrences with single space
        content = ' '.join(
            word for word in content.split() 
            if word.lower() != 'nan'
        )
        
        # Clean up multiple spaces
        content = ' '.join(content.split())
        
        return content
    
    def fix_excel_chunks(self):
        cur = self.conn.cursor()
        try:
            # Get chunks from Excel documents
            cur.execute("""
                SELECT c.id, c.content, d.title 
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.url LIKE '%.xls%'
                AND c.content LIKE '%NaN%'
            """)
            
            chunks = cur.fetchall()
            print(f"\nFound {len(chunks)} Excel chunks to clean")
            
            for chunk_id, content, title in chunks:
                try:
                    # Clean content
                    cleaned = self.clean_excel_content(content)
                    
                    # Update chunk
                    cur.execute("""
                        UPDATE chunks 
                        SET content = %s
                        WHERE id = %s
                    """, (cleaned, chunk_id))
                    
                    print(f"Cleaned chunk {chunk_id} from {title}")
                    
                except Exception as e:
                    print(f"Error cleaning chunk {chunk_id}: {e}")
                    continue
            
            self.conn.commit()
            
        finally:
            cur.close()
            self.conn.close()

def main():
    print("Starting Excel content cleanup...")
    processor = ExcelProcessor()
    processor.fix_excel_chunks()
    print("Cleanup complete!")

if __name__ == "__main__":
    main()