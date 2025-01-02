import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Fetch PostgreSQL URI from .env
POSTGRESQL_URI = os.getenv("POSTGRESQL_URI")


def get_db_size(cursor):
    """Get the total size of the database."""
    query = "SELECT pg_size_pretty(pg_database_size(current_database())) AS size;"
    cursor.execute(query)
    result = cursor.fetchone()
    return result["size"]


def get_table_sizes(cursor):
    """Get the sizes of individual tables."""
    query = """
        SELECT 
            relname AS table_name,
            pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
            pg_size_pretty(pg_relation_size(relid)) AS data_size,
            pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS index_size
        FROM pg_catalog.pg_statio_user_tables
        ORDER BY pg_total_relation_size(relid) DESC;
    """
    cursor.execute(query)
    return cursor.fetchall()


def get_recently_created_user_tables(cursor, limit=10):
    """
    Fetch the most recently created user-defined tables.
    """
    query = f"""
        SELECT 
            n.nspname AS schema_name,
            c.relname AS table_name,
            pg_size_pretty(pg_total_relation_size(c.oid)) AS table_size
        FROM 
            pg_class c
        JOIN 
            pg_namespace n ON n.oid = c.relnamespace
        WHERE 
            n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')  -- Exclude system schemas
            AND c.relkind = 'r'  -- Only include ordinary tables
        ORDER BY 
            c.oid DESC  -- Approximate creation order
        LIMIT {limit};
    """
    cursor.execute(query)
    return cursor.fetchall()





def main():
    if not POSTGRESQL_URI:
        print("Error: POSTGRESQL_URI is not set in .env")
        return

    # Connect to the database
    try:
        conn = psycopg2.connect(POSTGRESQL_URI)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get database size
        db_size = get_db_size(cursor)
        print(f"Total Database Size: {db_size}")

        # Get table sizes
        table_sizes = get_table_sizes(cursor)
        print("\nTable Sizes:")
        for table in table_sizes:
            print(f"Table: {table['table_name']}, Total Size: {table['total_size']}, "
                  f"Data Size: {table['data_size']}, Index Size: {table['index_size']}")

        # Get recently created or modified tables
        days_to_check = 1  # Adjust as needed
        recent_tables = get_recently_created_user_tables(cursor, limit=1)
        print(f"\nRecently Created or Modified Tables (Last {days_to_check} Days):")
        for table in recent_tables:
            print(f"Schema: {table['schema_name']}, Table: {table['table_name']}, "
                  f"Last Vacuum: {table['vacuum_time']}, Last Analyze: {table['analyze_time']}, "
                  f"Size: {table['table_size']}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
