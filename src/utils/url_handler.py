# src/utils/url_handler.py

import os
from urllib.parse import urlparse, quote, urljoin
from typing import Optional

import psycopg2

class URLHandler:
    """Handle URL management for ERCOT documents"""
    
    BASE_URL = "https://www.ercot.com"
    FILE_BASE = "/files/docs/"
    SERVICE_BASE = "/services/rq/"
    
    @classmethod
    def normalize_url(cls, url: str, file_name: Optional[str] = None) -> str:
        """Normalize URLs to standard ERCOT format"""
        if not url:
            return url
            
        # Remove version suffixes and clean spaces
        url = url.split('_v')[0]  # Remove _v1, _v2 etc.
        
        if url.startswith('file://'):
            # Convert file URL to ERCOT URL format
            if file_name:
                # Look up the original URL from the documents table
                return cls._get_original_url(file_name)
            return url
            
        if cls.BASE_URL in url:
            # Already an ERCOT URL
            parsed = urlparse(url)
            path = parsed.path
            
            # Remove any query parameters or versioning
            path = path.split('?')[0].split('_v')[0]
            
            # Check if it's a document URL
            if path.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
                # Ensure proper encoding of spaces and special characters
                filename = path.split('/')[-1]
                encoded_filename = quote(filename)
                base_path = '/'.join(path.split('/')[:-1])
                path = f"{base_path}/{encoded_filename}"
                
                # Ensure document URLs use /files/docs/
                if cls.SERVICE_BASE in path:
                    path = path.replace(cls.SERVICE_BASE, cls.FILE_BASE)
                
            return cls.BASE_URL + path
                
        return url

    @classmethod
    def _get_original_url(cls, file_name: str) -> str:
        """Get original ERCOT URL from filename"""
        # Look up the URL from your documents table
        # For now, construct a probable URL
        encoded_name = quote(file_name)
        return f"{cls.BASE_URL}{cls.FILE_BASE}{encoded_name}"

    @classmethod
    def get_document_url(cls, file_name: str, content_type: str) -> str:
        """Generate proper ERCOT URL for a document"""
        encoded_name = quote(file_name)
        if content_type == 'web':
            return urljoin(cls.BASE_URL + cls.SERVICE_BASE, encoded_name)
        else:
            return urljoin(cls.BASE_URL + cls.FILE_BASE, encoded_name)
    
    @staticmethod
    def get_complete_url(url: str, doc_title: str = None) -> str:
        """Get complete URL with proper file extension"""
        if not url:
            return url
            
        # If URL already includes file extension, return as is
        if any(url.lower().endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
            return url
            
        # Query database for correct URL
        conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        cur = conn.cursor()
        try:
            # Try exact match first
            cur.execute("""
                SELECT url 
                FROM documents 
                WHERE url LIKE %s || '%%'
                ORDER BY LENGTH(url) DESC  -- Get most complete URL
                LIMIT 1
            """, (url,))
            
            result = cur.fetchone()
            if result:
                return result[0]
                
            # If no match and we have title, try title match
            if doc_title:
                cur.execute("""
                    SELECT url 
                    FROM documents 
                    WHERE title = %s
                    LIMIT 1
                """, (doc_title,))
                
                result = cur.fetchone()
                if result:
                    return result[0]
                    
        finally:
            cur.close()
            conn.close()
            
        return url