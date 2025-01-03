from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
import logging
import psycopg2
from typing import List, Dict, Optional, Tuple
import time
import re
from datetime import datetime

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
        if not row:
            return {}
            
        content_type, file_name, url, created_at = row
        
        return {
            "document_type": file_name.split('.')[-1] if file_name else 'web',
            "last_updated": created_at.isoformat() if created_at else None,
            "url": url or f"document://{file_name}" if file_name else None
        }

    def extract_highlights(self, content: str, query_terms: List[str]) -> List[str]:
        """Extract relevant highlights from content"""
        highlights = []
        sentences = re.split('[.!?]+', content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Check if sentence contains query terms
            if any(term.lower() in sentence.lower() for term in query_terms):
                highlights.append(sentence)
                
        # If no highlights found, use first sentence
        if not highlights and sentences:
            highlights.append(sentences[0])
            
        return highlights[:3]  # Return top 3 highlights

    async def vector_search(self, query: str, k: int = 5) -> Tuple[List[Dict], Dict]:
        """Perform vector similarity search with enhanced metadata"""
        query_embedding = self.embeddings.embed_query(query)
        embedding_str = f"[{','.join(map(str, query_embedding))}]"
        
        cur = self.conn.cursor()
        
        # Get total sources first
        cur.execute("SELECT COUNT(DISTINCT document_id) FROM chunks")
        total_sources = cur.fetchone()[0]
        
        # Perform vector search
        cur.execute("""
            WITH chunk_data AS (
                SELECT 
                    c.id as chunk_id,
                    c.content,
                    c.document_id,
                    d.title,
                    d.content_type,
                    d.file_name,
                    d.url,
                    e.embedding,
                    (e.embedding <=> %s::vector) as distance
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                JOIN embeddings e ON c.id = e.chunk_id
                ORDER BY e.embedding <=> %s::vector
                LIMIT %s
            )
            SELECT * FROM chunk_data
        """, (embedding_str, embedding_str, k))
        
        chunks = []
        seen_docs = set()
        query_terms = query.lower().split()
        
        for row in cur.fetchall():
            (chunk_id, content, doc_id, title, content_type, 
             file_name, url, _, distance) = row
             
            # Get document metadata
            metadata = self.get_document_metadata(doc_id)
            
            # Generate preview and highlights
            preview = content[:200] + "..." if len(content) > 200 else content
            highlights = self.extract_highlights(content, query_terms)
            
            chunks.append({
                'chunk_id': chunk_id,
                'content': content.strip(),
                'metadata': {
                    'document_id': doc_id,
                    'title': title,
                    'url': metadata['url'],
                    'type': content_type,
                    'document_type': metadata['document_type'],
                    'last_updated': metadata['last_updated']
                },
                'preview': preview,
                'highlights': highlights,
                'distance': float(distance)
            })
            
            seen_docs.add(doc_id)
        
        search_metadata = {
            'total_sources': total_sources,
            'sources_used': len(seen_docs)
        }
        
        return chunks, search_metadata

    def extract_citations(self, text: str) -> Tuple[str, List[Citation]]:
        """Extract citations from generated text"""
        citations = []
        modified_text = text
        
        # Find citations in [Source] format
        citation_pattern = r'\[(.*?)\]'
        matches = re.finditer(citation_pattern, text)
        
        offset = 0
        for match in matches:
            start = match.start() - offset
            end = match.end() - offset
            source = match.group(1)
            
            citations.append(Citation(
                title=source,
                start_idx=start,
                end_idx=end
            ))
            
            # Remove citation from text
            modified_text = modified_text[:start] + modified_text[end:]
            offset += end - start
        
        return modified_text, citations

    def create_prompt(self, query: str, chunks: List[Dict]) -> str:
        """Create enhanced prompt with context"""
        sources_text = []
        
        for chunk in chunks:
            source = "[{title}]".format(
                title=chunk['metadata']['title'].replace('_', ' ').title()
            )
            content = chunk['content']
            sources_text.append(f"{source}: {content}")
        
        return f"""You are an expert assistant helping users understand ERCOT registration and qualification processes. 
        Answer the following question using the provided sources: "{query}"

        Guidelines:
        1. Start with a direct answer to the question
        2. Use clear structure with paragraphs and numbered lists for steps
        3. Cite sources using [Document Title] format - ALWAYS include citations
        4. Make citations frequency - aim for at least one citation per paragraph
        5. Highlight key terms or requirements
        6. If sources lack information, be explicit about it
        7. Be concise but comprehensive

        Sources:
        {chr(10).join(sources_text)}

        Answer the question with frequent citations:"""

    async def process_query(self, query: str) -> Dict:
        """Process query with enhanced response format"""
        start_time = time.time()
        
        # Get relevant chunks with metadata
        chunks, search_metadata = await self.vector_search(query)
        
        if not chunks:
            return {
                'answer': "I couldn't find relevant information in the ERCOT documentation.",
                'citations': [],
                'sources': [],
                'processing_time': time.time() - start_time,
                'metadata': search_metadata
            }
        
        # Create prompt and get response
        prompt = self.create_prompt(query, chunks)
        response = await self.llm.ainvoke(prompt)
        
        # Extract citations
        clean_answer, citations = self.extract_citations(response.content)
        
        # Process sources
        sources = []
        seen_docs = set()
        
        for chunk in chunks:
            doc_id = chunk['metadata']['document_id']
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                sources.append({
                    'title': chunk['metadata']['title'],
                    'url': chunk['metadata']['url'],
                    'type': chunk['metadata']['type'],
                    'content': chunk['content'],
                    'metadata': {
                        'document_type': chunk['metadata']['document_type'],
                        'last_updated': chunk['metadata']['last_updated']
                    },
                    'preview': chunk['preview'],
                    'highlights': chunk['highlights'],
                    'relevance': 1 - chunk['distance']
                })
        
        # Add token count to metadata
        search_metadata['token_count'] = len(clean_answer.split())
        
        return {
            'answer': clean_answer,
            'citations': [vars(c) for c in citations],
            'sources': sources,
            'processing_time': time.time() - start_time,
            'metadata': search_metadata
        }

    def __del__(self):
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except:
            pass