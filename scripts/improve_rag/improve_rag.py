# scripts/improve_rag.py
import os
import psycopg2
from dotenv import load_dotenv
import logging
from typing import List, Dict
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO)

class RAGImprover:
    def __init__(self):
        load_dotenv()
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
    
    def analyze_urls(self):
        """Analyze current URLs in database"""
        cur = self.conn.cursor()
        try:
            # Find similar URLs
            cur.execute("""
                WITH url_patterns AS (
                    SELECT 
                        id,
                        title,
                        url,
                        content_type,
                        REGEXP_REPLACE(url, '_v\d+|_ver\d+(\.\w+)?$', '') as base_url
                    FROM documents
                )
                SELECT 
                    base_url,
                    array_agg(url) as urls,
                    array_agg(title) as titles
                FROM url_patterns
                GROUP BY base_url
                HAVING COUNT(*) > 1
                ORDER BY base_url;
            """)
            
            duplicates = cur.fetchall()
            print(f"\nFound {len(duplicates)} URL patterns with variations:")
            for base, urls, titles in duplicates:
                print(f"\nBase URL: {base}")
                for url, title in zip(urls, titles):
                    print(f"- {title}: {url}")
            
        finally:
            cur.close()
    
    def deduplicate_sources(self):
        """Update source citations to avoid duplication"""
        cur = self.conn.cursor()
        try:
            # Group similar documents
            cur.execute("""
                WITH similar_docs AS (
                    SELECT 
                        MIN(id) as canonical_id,
                        array_agg(id) as doc_ids,
                        title
                    FROM documents
                    GROUP BY title
                    HAVING COUNT(*) > 1
                )
                SELECT * FROM similar_docs;
            """)
            
            duplicates = cur.fetchall()
            print(f"\nFound {len(duplicates)} document titles with multiple entries")
            
            for canonical_id, doc_ids, title in duplicates:
                other_ids = [id for id in doc_ids if id != canonical_id]
                if other_ids:
                    print(f"\nProcessing {title}")
                    print(f"Canonical ID: {canonical_id}")
                    print(f"Other IDs: {other_ids}")
                    
                    # Update chunks to reference canonical document
                    cur.execute("""
                        UPDATE chunks 
                        SET document_id = %s
                        WHERE document_id = ANY(%s)
                    """, (canonical_id, other_ids))
                    
                    # Remove duplicates
                    cur.execute("""
                        DELETE FROM documents 
                        WHERE id = ANY(%s)
                    """, (other_ids,))
            
            self.conn.commit()
            
        finally:
            cur.close()
    
    def update_document_types(self):
        """Update document content types based on actual content"""
        cur = self.conn.cursor()
        try:
            # Set proper content types based on URLs and content
            cur.execute("""
                UPDATE documents 
                SET content_type = CASE
                    WHEN url LIKE '%.pdf' THEN 'pdf'
                    WHEN url LIKE '%.doc%' THEN 'doc'
                    WHEN url LIKE '%.xls%' THEN 'excel'
                    WHEN url NOT LIKE '%/files/docs/%' THEN 'web'
                    ELSE content_type
                END
                WHERE id IN (
                    SELECT id FROM documents
                    WHERE content_type IN ('document', 'web')
                )
                RETURNING id, title, content_type;
            """)
            
            updated = cur.fetchall()
            print(f"\nUpdated {len(updated)} document types:")
            for id, title, type in updated:
                print(f"- {title}: {type}")
            
            self.conn.commit()
            
        finally:
            cur.close()
    
    def improve_all(self):
        """Run all improvements"""
        try:
            print("Starting RAG improvements...")
            
            print("\n1. Analyzing URLs...")
            self.analyze_urls()
            
            print("\n2. Deduplicating sources...")
            self.deduplicate_sources()
            
            print("\n3. Updating document types...")
            self.update_document_types()
            
            print("\nImprovements complete!")
            
        finally:
            self.conn.close()

if __name__ == "__main__":
    improver = RAGImprover()
    improver.improve_all()