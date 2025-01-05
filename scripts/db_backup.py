# scripts/db_backup.py
import os
import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)

class DatabaseBackup:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        
    def backup_table(self, table_name: str, backup_dir: str) -> int:
        cur = self.conn.cursor()
        count = 0
        
        try:
            # Create backup directory if it doesn't exist
            os.makedirs(backup_dir, exist_ok=True)
            
            # Get all data from table
            cur.execute(f"SELECT * FROM {table_name}")
            rows = cur.fetchall()
            
            # Get column names
            cur.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            columns = [col[0] for col in cur.fetchall()]
            
            # Create list of dictionaries
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Handle special data types
                    if isinstance(row[i], datetime):
                        row_dict[col] = row[i].isoformat()
                    elif isinstance(row[i], (bytes, bytearray)):
                        row_dict[col] = list(row[i])
                    else:
                        row_dict[col] = row[i]
                data.append(row_dict)
            
            # Write to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(backup_dir, f"{table_name}_{timestamp}.json")
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            count = len(rows)
            logging.info(f"Backed up {count} rows from {table_name} to {filename}")
            
        except Exception as e:
            logging.error(f"Error backing up {table_name}: {e}")
            raise
        finally:
            cur.close()
            
        return count

    def backup_all(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"backups/backup_{timestamp}"
            
            tables = ['documents', 'chunks', 'embeddings']
            total_rows = 0
            
            for table in tables:
                rows = self.backup_table(table, backup_dir)
                total_rows += rows
            
            logging.info(f"""
Backup completed:
- Location: {backup_dir}
- Tables: {', '.join(tables)}
- Total rows: {total_rows}
""")
            
        finally:
            self.conn.close()

def main():
    print("Starting database backup...")
    backup = DatabaseBackup()
    backup.backup_all()
    print("Backup complete!")

if __name__ == "__main__":
    main()