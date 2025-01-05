# rag_url_check.py
import os
import psycopg2
from dotenv import load_dotenv
import logging
from typing import Dict, List, Set
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rag_url_check.log"),
        logging.StreamHandler()
    ]
)

def get_connection():
    """Get database connection"""
    load_dotenv()
    return psycopg2.connect(os.getenv("POSTGRESQL_URI"))

def check_rag_urls():
    """Check consistency between documents, chunks, and embeddings"""
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Get documents that have chunks and embeddings
        cur.execute("""
            WITH doc_stats AS (
                SELECT 
                    d.id as doc_id,
                    d.url,
                    d.title,
                    d.content_type,
                    d.file_name,
                    COUNT(DISTINCT c.id) as chunk_count,
                    COUNT(DISTINCT e.id) as embedding_count
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                LEFT JOIN embeddings e ON c.id = e.chunk_id
                GROUP BY d.id, d.url, d.title, d.content_type, d.file_name
            )
            SELECT * FROM doc_stats
            ORDER BY doc_id;
        """)
        
        results = []
        for row in cur.fetchall():
            (doc_id, url, title, content_type, file_name, 
             chunk_count, embedding_count) = row
            
            results.append({
                'doc_id': doc_id,
                'url': url,
                'title': title,
                'content_type': content_type,
                'file_name': file_name,
                'chunks': chunk_count,
                'embeddings': embedding_count,
                'has_chunks': chunk_count > 0,
                'has_embeddings': embedding_count > 0,
                'complete': chunk_count > 0 and embedding_count > 0
            })
        
        df = pd.DataFrame(results)
        
        # Summary statistics
        print("\nRAG System URL Check Results:")
        print("-" * 50)
        print(f"Total documents: {len(df)}")
        print(f"Documents with chunks: {df['has_chunks'].sum()}")
        print(f"Documents with embeddings: {df['has_embeddings'].sum()}")
        print(f"Complete documents: {df['complete'].sum()}")
        
        # Check web content
        web_content = df[df['content_type'] == 'web']
        print("\nWeb Content:")
        print(f"Total web documents: {len(web_content)}")
        print(f"Web docs with chunks: {web_content['has_chunks'].sum()}")
        print(f"Web docs with embeddings: {web_content['has_embeddings'].sum()}")
        
        # Check file documents
        file_docs = df[df['content_type'] == 'document']
        print("\nFile Documents:")
        print(f"Total file documents: {len(file_docs)}")
        print(f"File docs with chunks: {file_docs['has_chunks'].sum()}")
        print(f"File docs with embeddings: {file_docs['has_embeddings'].sum()}")
        
        # Check for inconsistencies
        inconsistent = df[
            (df['has_chunks'] != df['has_embeddings']) |
            (df['chunks'] != df['embeddings'])
        ]
        
        if not inconsistent.empty:
            print("\nInconsistent Documents:")
            print("-" * 50)
            for _, row in inconsistent.iterrows():
                print(f"\nDocument ID: {row['doc_id']}")
                print(f"Title: {row['title']}")
                print(f"URL: {row['url']}")
                print(f"Chunks: {row['chunks']}")
                print(f"Embeddings: {row['embeddings']}")
        
        # Save detailed results
        df.to_csv('rag_url_check_results.csv', index=False)
        print("\nDetailed results saved to 'rag_url_check_results.csv'")
        
        # Check if any chunks point to non-existent documents
        cur.execute("""
            SELECT c.id, c.document_id 
            FROM chunks c 
            LEFT JOIN documents d ON c.document_id = d.id 
            WHERE d.id IS NULL;
        """)
        orphaned_chunks = cur.fetchall()
        if orphaned_chunks:
            print("\nWarning: Found orphaned chunks!")
            print(f"Number of orphaned chunks: {len(orphaned_chunks)}")
        
        # Check if any embeddings point to non-existent chunks
        cur.execute("""
            SELECT e.id, e.chunk_id 
            FROM embeddings e 
            LEFT JOIN chunks c ON e.chunk_id = c.id 
            WHERE c.id IS NULL;
        """)
        orphaned_embeddings = cur.fetchall()
        if orphaned_embeddings:
            print("\nWarning: Found orphaned embeddings!")
            print(f"Number of orphaned embeddings: {len(orphaned_embeddings)}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_rag_urls()