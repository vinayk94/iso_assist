# scripts/diagnose_rag.py
import os
import psycopg2
from dotenv import load_dotenv
import logging
from typing import List, Dict
import json

logging.basicConfig(level=logging.INFO)

class RAGDiagnostic:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        
    def check_documents(self):
        """Check documents table for our key documents"""
        cur = self.conn.cursor()
        try:
            print("\n1. CHECKING DOCUMENTS:")
            print("-" * 50)
            
            # Check documents with /files/docs/
            cur.execute("""
                SELECT id, title, url 
                FROM documents 
                WHERE url LIKE '%/files/docs/%'
                AND (
                    title LIKE '%INR%' 
                    OR title LIKE '%Resource%'
                    OR title LIKE '%DER%'
                    OR title LIKE '%Generation%'
                )
                ORDER BY title;
            """)
            
            docs = cur.fetchall()
            print(f"\nFound {len(docs)} relevant documents:")
            for doc_id, title, url in docs:
                print(f"\nID: {doc_id}")
                print(f"Title: {title}")
                print(f"URL: {url}")
                
            return [doc[0] for doc in docs]  # Return doc_ids for next check
            
        finally:
            cur.close()
    
    def check_chunks(self, doc_ids: List[int]):
        """Check chunks for these documents"""
        cur = self.conn.cursor()
        try:
            print("\n2. CHECKING CHUNKS:")
            print("-" * 50)
            
            cur.execute("""
                SELECT 
                    d.title,
                    COUNT(c.id) as chunk_count,
                    MIN(LENGTH(c.content)) as min_length,
                    MAX(LENGTH(c.content)) as max_length,
                    AVG(LENGTH(c.content)) as avg_length
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                WHERE d.id = ANY(%s)
                GROUP BY d.id, d.title
                ORDER BY d.title;
            """, (doc_ids,))
            
            chunks = cur.fetchall()
            print(f"\nChunk statistics for {len(chunks)} documents:")
            for title, count, min_len, max_len, avg_len in chunks:
                print(f"\nDocument: {title}")
                print(f"Chunks: {count}")
                print(f"Min length: {min_len}")
                print(f"Max length: {max_len}")
                print(f"Avg length: {avg_len:.1f}")
                
            # Get sample chunk content
            cur.execute("""
                SELECT d.title, c.content 
                FROM documents d
                JOIN chunks c ON d.id = c.document_id
                WHERE d.id = ANY(%s)
                LIMIT 2;
            """, (doc_ids,))
            
            print("\nSample chunks:")
            for title, content in cur.fetchall():
                print(f"\nFrom {title}:")
                print(content[:200] + "...")
                
        finally:
            cur.close()
    
    def check_embeddings(self, doc_ids: List[int]):
        """Check embeddings for these documents"""
        cur = self.conn.cursor()
        try:
            print("\n3. CHECKING EMBEDDINGS:")
            print("-" * 50)
            
            cur.execute("""
                WITH chunk_counts AS (
                    SELECT d.id, d.title, COUNT(c.id) as chunks
                    FROM documents d
                    LEFT JOIN chunks c ON d.id = c.document_id
                    WHERE d.id = ANY(%s)
                    GROUP BY d.id, d.title
                ),
                embedding_counts AS (
                    SELECT d.id, COUNT(e.id) as embeddings
                    FROM documents d
                    LEFT JOIN chunks c ON d.id = c.document_id
                    LEFT JOIN embeddings e ON c.id = e.chunk_id
                    WHERE d.id = ANY(%s)
                    GROUP BY d.id
                )
                SELECT 
                    cc.title,
                    cc.chunks,
                    COALESCE(ec.embeddings, 0) as embeddings
                FROM chunk_counts cc
                LEFT JOIN embedding_counts ec ON cc.id = ec.id
                ORDER BY cc.title;
            """, (doc_ids, doc_ids))
            
            stats = cur.fetchall()
            print("\nEmbedding coverage:")
            for title, chunks, embeddings in stats:
                print(f"\nDocument: {title}")
                print(f"Chunks: {chunks}")
                print(f"Embeddings: {embeddings}")
                if chunks != embeddings:
                    print("WARNING: Not all chunks have embeddings!")
                    
        finally:
            cur.close()
    
    def test_vector_search(self):
        """Test vector search with a specific query"""
        cur = self.conn.cursor()
        try:
            print("\n4. TESTING VECTOR SEARCH:")
            print("-" * 50)
            
            # Test query
            query = "how to create an INR for a Generation Resource Under 10 MW"
            print(f"\nTest query: {query}")
            
            # Get relevant chunks without vector search first
            cur.execute("""
                SELECT 
                    d.title,
                    c.content
                FROM documents d
                JOIN chunks c ON d.id = c.document_id
                WHERE d.title LIKE '%INR%'
                OR d.title LIKE '%Resource%'
                OR d.title LIKE '%Generation%'
                LIMIT 5;
            """)
            
            print("\nRelevant chunks without vector search:")
            for title, content in cur.fetchall():
                print(f"\nFrom {title}:")
                print(content[:200] + "...")
            
        finally:
            cur.close()
    
    def run_diagnostics(self):
        """Run all diagnostic checks"""
        try:
            doc_ids = self.check_documents()
            self.check_chunks(doc_ids)
            self.check_embeddings(doc_ids)
            self.test_vector_search()
            
        finally:
            self.conn.close()

if __name__ == "__main__":
    diagnostic = RAGDiagnostic()
    diagnostic.run_diagnostics()