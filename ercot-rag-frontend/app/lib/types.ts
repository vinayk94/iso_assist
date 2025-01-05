// app/lib/types.ts

export interface Citation {
    title: string;
    start_idx: number;
    end_idx: number;
}

export interface SourceMetadata {
    document_id: number;
    title: string;
    type: string;
    url: string;
    created_at: string;
}

export interface Source {
    chunk_id: number;
    content: string;
    metadata: SourceMetadata;
    highlights: string[];
    relevance: number;
}

export interface QueryMetadata {
    total_chunks: number;
    unique_sources: number;
    processing_time: number;
}

export interface RAGResponse {
    answer: string;
    citations: Citation[];
    sources: Source[];
    metadata: QueryMetadata;
    error?: string;
}