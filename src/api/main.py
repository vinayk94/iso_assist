from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import logging
from datetime import datetime
import time

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))


from src.assistant.rag_assistant import ERCOTRAGAssistant



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Pydantic models
class Citation(BaseModel):
    """Citation in generated text"""
    title: str
    start_idx: int
    end_idx: int

class DocumentMetadata(BaseModel):
    """Document metadata"""
    document_type: str
    last_updated: Optional[str]

class Source(BaseModel):
    """Enhanced source information"""
    title: str
    url: Optional[str]
    type: str
    content: str
    metadata: DocumentMetadata
    preview: str
    highlights: List[str]
    relevance: float

class QueryMetadata(BaseModel):
    """Query processing metadata"""
    total_sources: int
    sources_used: int
    token_count: int

class QueryResponse(BaseModel):
    """Enhanced RAG response"""
    answer: str
    citations: List[Citation]
    sources: List[Source]
    processing_time: float
    metadata: QueryMetadata

class QueryRequest(BaseModel):
    """Query request with options"""
    query: str
    max_sources: Optional[int] = Field(5, ge=1, le=10)
    include_metadata: Optional[bool] = True

# Initialize FastAPI
app = FastAPI(
    title="ERCOT RAG API",
    description="Enhanced Retrieval Augmented Generation API for ERCOT documentation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process an ERCOT documentation query with enhanced response format
    """
    try:
        logger.info(f"Processing query: {request.query}")
        query_start = time.time()
        
        # Get RAG assistant
        assistant = await ERCOTRAGAssistant.get_instance()
        
        # Process query
        result = await assistant.process_query(request.query)
        
        # Format sources
        sources = [
            Source(
                title=src['title'],
                url=src['url'],
                type=src['type'],
                content=src['content'],
                metadata=DocumentMetadata(
                    document_type=src['metadata']['document_type'],
                    last_updated=src['metadata']['last_updated']
                ),
                preview=src['preview'],
                highlights=src['highlights'],
                relevance=src['relevance']
            )
            for src in result['sources'][:request.max_sources]
        ]
        
        # Construct response
        response = QueryResponse(
            answer=result['answer'],
            citations=result['citations'],
            sources=sources,
            processing_time=result['processing_time'],
            metadata=QueryMetadata(
                total_sources=result['metadata']['total_sources'],
                sources_used=result['metadata']['sources_used'],
                token_count=result['metadata']['token_count']
            )
        )
        
        # Log response summary
        logger.info(
            f"Query processed in {result['processing_time']:.2f}s with "
            f"{len(sources)} sources and {len(result['citations'])} citations"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Query processing failed",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/api/health")
async def health_check():
    """
    Check API health status and system statistics
    """
    try:
        assistant = await ERCOTRAGAssistant.get_instance()
        
        # Check database connection and get stats
        with assistant.conn.cursor() as cur:
            # Get document counts
            cur.execute("""
                SELECT 
                    COUNT(*) as total_documents,
                    COUNT(CASE WHEN content_type = 'web' THEN 1 END) as web_documents,
                    COUNT(CASE WHEN content_type = 'document' THEN 1 END) as local_documents
                FROM documents
            """)
            doc_counts = cur.fetchone()
            
            # Get chunk and embedding counts
            cur.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM chunks) as total_chunks,
                    (SELECT COUNT(*) FROM embeddings) as total_embeddings
            """)
            chunk_counts = cur.fetchone()
            
        return {
            "status": "healthy",
            "database": "connected",
            "documents": {
                "total": doc_counts[0],
                "web_content": doc_counts[1],
                "local_documents": doc_counts[2]
            },
            "chunks": chunk_counts[0],
            "embeddings": chunk_counts[1],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Health check failed",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/api/sources")
async def get_sources():
    """
    Get list of available sources and their statistics
    """
    try:
        assistant = await ERCOTRAGAssistant.get_instance()
        
        with assistant.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    d.title,
                    d.content_type,
                    d.file_name,
                    COUNT(c.id) as chunk_count,
                    COUNT(e.id) as embedding_count,
                    d.created_at
                FROM documents d
                LEFT JOIN chunks c ON d.id = c.document_id
                LEFT JOIN embeddings e ON c.id = e.chunk_id
                GROUP BY d.id
                ORDER BY d.created_at DESC
            """)
            
            sources = []
            for row in cur.fetchall():
                title, content_type, file_name, chunks, embeddings, created_at = row
                sources.append({
                    "title": title,
                    "type": content_type,
                    "file_name": file_name,
                    "statistics": {
                        "chunks": chunks,
                        "embeddings": embeddings,
                        "processing_complete": chunks == embeddings
                    },
                    "added_at": created_at.isoformat()
                })
            
            return {
                "sources": sources,
                "total_count": len(sources),
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error fetching sources: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch sources",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@app.get("/api/docs/{document_id}/chunks")
async def get_document_chunks(document_id: int, limit: int = 10, offset: int = 0):
    """
    Get chunks for a specific document
    """
    try:
        assistant = await ERCOTRAGAssistant.get_instance()
        
        with assistant.conn.cursor() as cur:
            # Get document info
            cur.execute("""
                SELECT title, content_type, file_name
                FROM documents
                WHERE id = %s
            """, (document_id,))
            
            doc = cur.fetchone()
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail=f"Document {document_id} not found"
                )
                
            # Get chunks with pagination
            cur.execute("""
                SELECT 
                    c.id,
                    c.content,
                    c.chunk_index,
                    EXISTS(SELECT 1 FROM embeddings e WHERE e.chunk_id = c.id) as has_embedding
                FROM chunks c
                WHERE c.document_id = %s
                ORDER BY c.chunk_index
                LIMIT %s OFFSET %s
            """, (document_id, limit, offset))
            
            chunks = []
            for row in cur.fetchall():
                chunk_id, content, index, has_embedding = row
                chunks.append({
                    "id": chunk_id,
                    "content": content,
                    "index": index,
                    "has_embedding": has_embedding
                })
            
            return {
                "document": {
                    "id": document_id,
                    "title": doc[0],
                    "type": doc[1],
                    "file_name": doc[2]
                },
                "chunks": chunks,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(chunks)
                }
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document chunks: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to fetch document chunks",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)