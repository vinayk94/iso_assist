# src/api/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

class QueryRequest(BaseModel):
    query: str
    max_sources: int = 5

class Citation(BaseModel):
    title: str
    start_idx: int
    end_idx: int

class SourceMetadata(BaseModel):
    document_id: int
    title: str
    type: str
    url: str
    created_at: str

class Source(BaseModel):
    chunk_id: int
    content: str
    metadata: SourceMetadata
    highlights: List[str]
    relevance: float

class QueryMetadata(BaseModel):
    total_chunks: int
    unique_sources: int
    processing_time: float

class RAGResponse(BaseModel):
    answer: str
    citations: List[Citation]
    sources: List[Source]
    metadata: QueryMetadata
    error: Optional[str] = None