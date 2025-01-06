from urllib.parse import quote
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
import logging
import psycopg2
from typing import List, Dict, Optional, Tuple
import time
import re
from datetime import datetime
from src.utils.url_handler import URLHandler
import re

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

def get_api_key():
    """Get API key with proper environment handling"""
    if 'JINA_API_KEY' in os.environ:
        del os.environ['JINA_API_KEY']
    load_dotenv(override=True)
    return os.getenv("JINA_API_KEY")


class ERCOTEmbeddings:
    """Custom embeddings class for ERCOT documents"""
    def __init__(self, api_key: str, model_name: str = "jina-embeddings-v3"):
        self.api_key = api_key
        self.model_name = model_name
        self.dimension = 1024
        
    def embed_query(self, text: str) -> List[float]:
        import requests
        
        url = 'https://api.jina.ai/v1/embeddings'
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            "model": self.model_name,
            "dimensions": self.dimension,
            "input": [text]
        }
        
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]

class Citation:
    """Track citations in generated text"""
    def __init__(self, title: str, start_idx: int, end_idx: int):
        self.title = title
        self.start_idx = start_idx
        self.end_idx = end_idx

class ERCOTRAGAssistant:
    """Enhanced RAG Assistant for ERCOT documentation"""
    
    _instance = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        load_dotenv()
        
        self.embeddings = ERCOTEmbeddings(
            api_key=get_api_key()
        )
        
        self.conn = psycopg2.connect(os.getenv("POSTGRESQL_URI"))
        
        self.llm = ChatGroq(
            groq_api_key=os.getenv("GROQ_API_KEY"),
            model_name="mixtral-8x7b-32768",
            temperature=0.3,
            max_tokens=1024
        )
        self.url_handler = URLHandler()
        self.start_time = None

    def get_document_metadata(self, doc_id: int) -> Dict:
        """Get detailed document metadata"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT 
                content_type,
                file_name,
                url,
                created_at
            FROM documents 
            WHERE id = %s
        """, (doc_id,))
        
        row = cur.fetchone()

        if row:
            url = self.url_handler.normalize_url(row[2], row[1])  # normalize the URL
            return {
                "document_type": row[0],
                "last_updated": row[3].isoformat() if row[3] else None,
                "url": url
            }
    
        if not row:
            return {}
            
        content_type, file_name, url, created_at = row
        
        return {
            "document_type": file_name.split('.')[-1] if file_name else 'web',
            "last_updated": created_at.isoformat() if created_at else None,
            "url": url or f"document://{file_name}" if file_name else None
        }
    
    

    def extract_highlights(self, content: str, query_terms: List[str]) -> List[str]:
        """Extract meaningful highlights from content"""
        highlights = []
        sentences = re.split(r'[.!?]+', content)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Remove repetitive words
            sentence = re.sub(r'\b(\w+)\s+\1+\b', r'\1', sentence)

            # Add to highlights if query terms match
            if any(term.lower() in sentence.lower() for term in query_terms):
                highlights.append(sentence)

        return highlights[:3]  # Return top 3 highlights

    
    def clean_content(self, content: str) -> str:
        """Clean content from NaN and formatting issues"""
        if not content:
            return ""
            
        # Remove NaN values
        content = re.sub(r'\s*NaN\s*', ' ', content)
        
        # Remove multiple spaces
        content = re.sub(r'\s+', ' ', content)
        
        # Remove empty lines
        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
        
        return content.strip()



    async def vector_search(self, query: str, k: int = 5) -> List[Dict]:
        """Get relevant chunks with original URLs from database"""
        try:
            query_embedding = self.embeddings.embed_query(query)
            embedding_str = f"[{','.join(map(str, query_embedding))}]"
            
            cur = self.conn.cursor()
            
            # Simple query that preserves original URLs
            cur.execute("""
                WITH ranked_chunks AS (
                    SELECT 
                        c.id as chunk_id,
                        c.content,
                        c.document_id,
                        d.title,
                        d.content_type,
                        d.url,
                        d.created_at,
                        (e.embedding <=> %s::vector) as similarity_score
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    JOIN embeddings e ON c.id = e.chunk_id
                    ORDER BY e.embedding <=> %s::vector
                    LIMIT %s
                )
                SELECT * FROM ranked_chunks;
            """, (embedding_str, embedding_str, k))
            
            chunks = []
            seen_docs = set()
            
            for row in cur.fetchall():
                chunk_id, content, doc_id, title, content_type, url, created_at, score = row
                
                if doc_id in seen_docs:
                    continue
                    
                seen_docs.add(doc_id)
                
                cleaned_content = self.clean_content(content)
                chunks.append({
                    'chunk_id': chunk_id,
                    'content': cleaned_content,
                    'metadata': {
                        'document_id': doc_id,
                        'title': title,
                        'type': content_type,
                        'url': url,
                        'created_at': created_at.isoformat() if created_at else None
                    },
                    'highlights': self.extract_highlights(cleaned_content, query),  # Use cleaned content
                    'relevance': 1 - score
                })
            
            return chunks
                
        except Exception as e:
            logging.error(f"Error in vector search: {e}")
            raise


    def extract_highlights(self, content: str, query: str) -> List[str]:
        """Extract meaningful highlights from content"""
        query_terms = query.lower().split()
        sentences = re.split(r'[.!?]+', content)
        highlights = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Score sentence based on query relevance
            score = sum(term in sentence.lower() for term in query_terms)
            
            # Additional scoring for meaningful content
            if len(sentence.split()) >= 5:  # Minimum word requirement
                score += 1
            if any(term in sentence.lower() for term in ['must', 'should', 'required', 'important']):
                score += 1
                
            if score > 0 and sentence not in highlights:
                highlights.append(sentence)
                
        return highlights[:3]  # Return top 3 most relevant highlights
    

    def deduplicate_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Deduplicate sources while preserving best content"""
        unique_sources = {}
        
        for chunk in chunks:
            doc_id = chunk['metadata']['document_id']
            
            if doc_id not in unique_sources:
                unique_sources[doc_id] = chunk
            else:
                # Keep source with higher relevance
                if chunk['relevance'] > unique_sources[doc_id]['relevance']:
                    unique_sources[doc_id] = chunk
                
                # Merge highlights if they're different
                existing_highlights = set(unique_sources[doc_id]['highlights'])
                for highlight in chunk['highlights']:
                    if highlight not in existing_highlights:
                        unique_sources[doc_id]['highlights'].append(highlight)
                        if len(unique_sources[doc_id]['highlights']) > 3:
                            break
        
        return list(unique_sources.values())
    
    def verify_source_url(self, source_id: int) -> Dict:
        """Verify and get source URL information"""
        cur = self.conn.cursor()
        try:
            cur.execute("""
                SELECT 
                    url, 
                    content_type,
                    file_name,
                    title
                FROM documents 
                WHERE id = %s
            """, (source_id,))
            
            row = cur.fetchone()
            if not row:
                return None
                
            url, content_type, file_name, title = row
            normalized_url = self.url_handler.normalize_url(url, file_name)
            
            return {
                'url': normalized_url,
                'type': content_type,
                'title': title
            }
        finally:
            cur.close()


    def create_prompt(self, query: str, sources: List[Dict]) -> str:
        source_text = []

        for source in sources:
            metadata = source['metadata']
            source_text.append(f"""
            [{metadata['title']}] (ID: {metadata['document_id']}, Type: {metadata['type']}):
            Content:
            {source['content']}
            Reference: {metadata['url']}
            """.strip())

        return f"""You are an expert assistant for ERCOT documentation. Answer the following question using ONLY the provided sources.

        Question: {query}

        Guidelines:
        1. Include citations inline where they are relevant.
        2. Use the format <cite data-source-id="[Document ID]">[Document Title]</cite> to refer to sources.
        3. Write in a clear, professional tone.
        4. Organize your response with headings (`<h3>`, `<h4>`), paragraphs (`<p>`), and lists (`<ol>`, `<ul>`) as needed.
        5. Avoid repeating information unnecessarily.
        6. Keep the response concise and actionable.
        7. Use HTML formatting for clarity and structure.

        Example:
        <h3>Registering a DER in ERCOT</h3>
        <p>Registering a Distributed Energy Resource (DER) in ERCOT involves completing the registration form and obtaining an ESR Dispatch Asset Code.</p>

        <h4>Step 1: Completing the Registration Form</h4>
        <p>To register a DER, download the appropriate form from the ERCOT website. You can use the <cite data-source-id="123">NOIE Identification and Meter Point Registration Form</cite> for non-scheduled entities, or the <cite data-source-id="124">ELSE Identification and Meter Point Registration Form</cite> for generators with a capacity of 1 MW or greater.</p>

        <h4>Step 2: Obtaining an ESR Dispatch Asset Code</h4>
        <p>After completing the registration form, download the <cite data-source-id="125">RIOO Export Spreadsheet</cite> to assign an ESR Dispatch Asset Code. Submit the completed spreadsheet to ERCOT.</p>

        Sources:
        {chr(10).join(source_text)}

        The response must be structured with embedded citations and valid HTML."""








    
    def start_processing(self):
        """Start timing the processing"""
        self.start_time = time.perf_counter()

    def get_processing_time(self) -> float:
        """Get elapsed processing time in seconds"""
        if self.start_time is None:
            return 0.0
        return  round(time.perf_counter() - self.start_time, 2)
    
    
    def format_answer(self, answer: str) -> str:
        """Format and clean the answer HTML"""
        # Remove Markdown-style lists to avoid conflicts
        answer = re.sub(r'^\d+\.\s+', r'<li>', answer, flags=re.MULTILINE)
        answer = re.sub(r'^\*\s+', r'<li>', answer, flags=re.MULTILINE)

        # Ensure proper list nesting
        answer = re.sub(r'(<li>.*?)(?=<li>|$)', r'\1</li>', answer)
        answer = re.sub(r'((?:<li>.*?</li>)+)', r'<ol>\1</ol>', answer)

        # Add paragraphs
        paragraphs = answer.split('\n\n')
        formatted_paragraphs = []
        for p in paragraphs:
            if not p.strip():
                continue
            if not (p.startswith('<') and p.endswith('>')):
                p = f'<p>{p}</p>'
            formatted_paragraphs.append(p)

        return '\n'.join(formatted_paragraphs)

    
    def extract_citations(self, text: str) -> List[Dict]:
        """Extract citations with source IDs"""
        citations = []
        citation_pattern = r'<cite data-source-id="(\d+)">\[(.*?)\]</cite>'
        
        for match in re.finditer(citation_pattern, text):
            source_id = match.group(1)
            title = match.group(2)
            citations.append({
                'title': title,
                'source_id': int(source_id),
                'start_idx': match.start(),
                'end_idx': match.end()
            })
        
        return citations
    
    def verify_and_fix_url(self, doc_id: int, url: str) -> str:
        """Verify and fix document URL"""
        cur = self.conn.cursor()
        try:
            # Get the complete document information - simplified query first
            cur.execute("""
                SELECT 
                    d.url, 
                    d.content_type,
                    d.file_name,
                    d.title
                FROM documents d
                WHERE d.id = %s
            """, (doc_id,))
            
            row = cur.fetchone()
            if not row:
                return url
                
            current_url, content_type, file_name, title = row
            
            # If it's not a document type, return current URL
            if content_type != 'document':
                return current_url
                
            # For documents, check if we have a proper URL with extension
            if file_name:
                # Try to find the correct URL
                cur.execute("""
                    SELECT url 
                    FROM documents 
                    WHERE title = %s 
                    AND url LIKE '%/files/docs/%'
                    AND url SIMILAR TO '%\.(pdf|doc|docx|xls|xlsx)$'
                    LIMIT 1
                """, (title,))
                
                correct_url_row = cur.fetchone()
                if correct_url_row:
                    return correct_url_row[0]
                    
                # If no correct URL found but we have file_name
                ext = os.path.splitext(file_name)[1]
                if ext and not current_url.lower().endswith(tuple(['.pdf', '.doc', '.docx', '.xls', '.xlsx'])):
                    # Remove any version suffixes and add extension
                    base_url = re.sub(r'_v\d+$|_ver\d+$', '', current_url)
                    return f"{base_url}{ext}"
            
            return current_url
                
        except Exception as e:
            logging.error(f"Error verifying URL for doc_id {doc_id}: {e}")
            return url  # Return original URL if any error occurs
        finally:
            cur.close()

    def clean_llm_response(self, response: str) -> str:
        """Clean up LLM response to ensure single, clean HTML content"""
        # Remove markdown-style formatting if present
        response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)
        
        # Extract HTML content if mixed formats exist
        html_match = re.search(r'<[ph][^>]*>.*</[ph]>', response, re.DOTALL)
        if html_match:
            return html_match.group(0)
            
        # If no HTML found, convert plain text to HTML
        if not response.strip().startswith('<'):
            lines = response.split('\n')
            formatted = []
            in_list = False
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith(('1.', '2.', '3.')):
                    if not in_list:
                        formatted.append('<ol>')
                        in_list = True
                    formatted.append(f'<li>{line[2:].strip()}</li>')
                else:
                    if in_list:
                        formatted.append('</ol>')
                        in_list = False
                    formatted.append(f'<p>{line}</p>')
            
            if in_list:
                formatted.append('</ol>')
                
            return '\n'.join(formatted)
            
        return response
    
    
    


    def enforce_consistent_html(self,html: str) -> str:
        # Normalize headings (allow <h3>, <h4>, etc.)
        html = re.sub(r'<h[1-6]>', '<h3>', html)
        html = re.sub(r'</h[1-6]>', '</h3>', html)

        # Remove redundant or empty tags
        html = re.sub(r'<h3>\s*</h3>', '', html)  # Remove empty headings

        # Fix nested lists
        html = re.sub(r'<ol>\s*<ol>', '<ol>', html)  # Remove nested <ol>
        html = re.sub(r'</ol>\s*</ol>', '</ol>', html)  # Close properly
        html = re.sub(r'<ul>\s*<ul>', '<ul>', html)  # Remove nested <ul>
        html = re.sub(r'</ul>\s*</ul>', '</ul>', html)  # Close properly

        # Fix list items
        html = re.sub(r'<li>\s*<li>', '<li>', html)  # Merge nested <li>
        html = re.sub(r'</li>\s*</li>', '</li>', html)  # Close duplicate <li>

        # Remove extra spaces between tags
        html = re.sub(r'>\s+<', '><', html).strip()

        return html





    async def process_query(self, query: str) -> Dict:
        try:
            self.start_processing()
            
            chunks = await self.vector_search(query)
            if not chunks:
                return {
                    'answer': """<p>I couldn't find relevant information for your query. 
                            Please try rephrasing your question or being more specific.</p>""",
                    'citations': [],
                    'sources': [],
                    'metadata': {
                        'total_chunks': 0,
                        'unique_sources': 0,
                        'processing_time': self.get_processing_time()
                    }
                }
            
            # Verify URLs before deduplication
            for chunk in chunks:
                chunk['metadata']['url'] = self.verify_and_fix_url(
                    chunk['metadata']['document_id'],
                    chunk['metadata']['url']
                )
            
            unique_sources = self.deduplicate_sources(chunks)
            context = self.create_prompt(query, unique_sources)
            response = await self.llm.ainvoke(context)
            answer = response.content if hasattr(response, 'content') else str(response)
            formatted_answer = self.format_answer(answer)

            citations = self.extract_citations(formatted_answer)
            consistent_answer = self.enforce_consistent_html(formatted_answer)

            logging.info(f"Metadata: {{'total_chunks': {len(chunks)}, 'unique_sources': {len(unique_sources)}, 'processing_time': {self.get_processing_time()}}}")

            logging.info(f"Raw model output: {formatted_answer}")
            logging.info(f"Processed output: {consistent_answer}")


            
            return {
                'answer': consistent_answer,
                'citations': citations,
                'sources': unique_sources,  # URLs already verified
                'metadata': {
                    'total_chunks': len(chunks),
                    'unique_sources': len(unique_sources),
                    'processing_time': self.get_processing_time()
                }
            }

        except Exception as e:
            logging.error(f"Error processing query: {e}")
            return {
                'answer': """<p>An error occurred while processing your query.</p>""",
                'error': str(e),
                'citations': [],
                'sources': [],
                'metadata': {
                    'total_chunks': 0,
                    'unique_sources': 0,
                    'processing_time': self.get_processing_time()
                }
            }
        
    def __del__(self):
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except:
            pass