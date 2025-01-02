import os
import logging
import psycopg2
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def register_documents(directory: str, conn):
    """Register local documents in the database."""
    cur = conn.cursor()
    registered = 0
    try:
        # Fetch existing files to avoid duplicates
        cur.execute("SELECT file_name FROM documents WHERE content_type = 'document'")
        existing_files = {row[0] for row in cur.fetchall()}

        for root, _, files in os.walk(directory):
            for file in files:
                abs_path = os.path.abspath(os.path.join(root, file))
                file_name = os.path.basename(abs_path)

                if file_name in existing_files:
                    logging.info(f"Skipping already registered file: {file}")
                    continue

                url = f"file://{abs_path.replace(os.sep, '/')}"
                if not os.path.exists(abs_path):
                    logging.warning(f"File path does not exist during registration: {abs_path}")
                    continue

                cur.execute("""
                    INSERT INTO documents (url, title, content_type, file_name)
                    VALUES (%s, %s, 'document', %s)
                    ON CONFLICT (url) DO NOTHING
                """, (url, file_name, file_name))

                registered += 1

        conn.commit()
        logging.info(f"Registered {registered} new documents")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error registering documents: {e}")
        raise
    finally:
        cur.close()

def check_unregistered_files(directory: str, conn):
    """Check for files that are not yet registered in the database."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT file_name FROM documents WHERE content_type = 'document'")
        registered_files = {row[0] for row in cur.fetchall()}

        unregistered_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file not in registered_files:
                    unregistered_files.append(file)

        if unregistered_files:
            logging.info(f"Found {len(unregistered_files)} unregistered files.")
            for file in unregistered_files[:5]:  # Show a sample
                logging.info(f"- {file}")
        else:
            logging.info("All files are already registered.")
    finally:
        cur.close()



if __name__ == "__main__":
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")

    if not postgres_uri:
        raise ValueError("POSTGRESQL_URI not found in environment")

    conn = psycopg2.connect(postgres_uri)
    try:
        #register_documents("data/documents", conn)
        check_unregistered_files("data/documents", conn)
    except Exception as e:
        logging.error(f"Failed to register documents: {e}")
    finally:
        conn.close()
