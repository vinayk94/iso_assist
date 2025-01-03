// app/lib/types.ts

export interface Citation {
    title: string;
    start_idx: number;
    end_idx: number;
}

export interface DocumentMetadata {
    document_type: string;
    last_updated?: string;
}

export interface Source {
    title: string;
    url?: string;
    type: string;
    content: string;
    metadata: DocumentMetadata;
    preview: string;
    highlights: string[];
    relevance: number;
}

export interface RAGResponse {
    query: string; // Use the correct type here
    answer: string;
    citations: Citation[];
    sources: Source[];
    processing_time: number;
    metadata: {
        total_sources: number;
        sources_used: number;
        token_count: number;
    };
}

