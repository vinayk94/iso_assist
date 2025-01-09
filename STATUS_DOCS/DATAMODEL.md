# RAG Application Data Model Design Document

## Requirements Analysis

### Core Requirements
1. **Content Management**
   - Store and retrieve ERCOT documentation
   - Maintain source traceability (URLs)
   - Support both web content and documents

2. **Search & Retrieval**
   - Semantic search using embeddings
   - Direct URL lookups for verification
   - Maintain chunk order for context

3. **Performance**
   - Fast similarity search for RAG queries
   - Efficient document reconstruction
   - Minimal overhead for maintenance

## Data Model Design

### 1. Documents Table
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);
```

**Design Decisions:**
- Only essential fields included
- URL uniqueness enforced to prevent duplicates
- No created_at field as temporal queries aren't needed
- Single index on URL for direct lookups

**Rationale:**
- RAG primarily needs source traceability
- Simple structure facilitates maintenance
- URL index supports quick verification lookups

### 2. URLs Table
```sql
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    content_type TEXT NOT NULL,  -- 'web' or 'document'
    is_processed BOOLEAN DEFAULT FALSE,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Design Decisions:**
- url as a unique identifier for deduplication.
- content_type to distinguish between web pages and - documents.
- is_processed to track scraping progress and prevent reprocessing.
- last_checked for monitoring and retry logic.

**Rationale:**
- Enables tracking of URLs encountered during scraping.
- Provides an audit trail for what has been processed.
- Helps in incremental scraping by focusing only on unprocessed URLs.
- Supports expandability to multiple sources without duplicating data.




### 3. Chunks Table
```sql
CREATE TABLE chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    chunk_index INTEGER
);
```

**Design Decisions:**
- CASCADE deletion to maintain referential integrity
- chunk_index for preserving document structure
- Single index on document_id for joins
- No metadata column to keep it simple

**Rationale:**
- Chunk order important for context
- Direct relationship to source document
- Clean deletion of related records

### 4. Embeddings Table
```sql
CREATE TABLE chunk_embeddings (
    id BIGSERIAL PRIMARY KEY,
    chunk_id BIGINT REFERENCES chunks(id) ON DELETE CASCADE,
    embedding vector(1024),
    model_version TEXT DEFAULT 'jina-embeddings-v3',
    tokens_used INTEGER
);
```

**Design Decisions:**
- HNSW index for vector similarity search
- One embedding per chunk enforced
- Model version tracked for future updates
- Token usage tracked for monitoring

**Rationale:**
- HNSW better than IVF-Flat for RAG:
  - More accurate for semantic search
  - Better with incremental updates
  - No parameter tuning needed

## Indexing Strategy

### Essential Indexes Only
```sql
CREATE INDEX idx_documents_url ON documents(url);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_embeddings_chunk ON chunk_embeddings(chunk_id);
CREATE INDEX idx_urls_processed ON urls(is_processed);
CREATE INDEX embedding_vector_idx ON chunk_embeddings USING hnsw (embedding vector_cosine_ops);
```

**Rationale:**
- Only indexes that support core RAG operations
- No temporal indexes as they're not needed
- is_processed index for incremental scraping.
- HNSW index for optimal similarity search
- Foreign key indexes for efficient joins

## Monitoring View
```sql
CREATE VIEW embedding_status AS
SELECT 
    COUNT(DISTINCT c.document_id) as total_documents,
    COUNT(DISTINCT CASE WHEN ce.id IS NOT NULL THEN c.document_id END) as embedded_documents,
    COUNT(DISTINCT c.id) as total_chunks,
    COUNT(DISTINCT ce.chunk_id) as embedded_chunks,
    COALESCE(SUM(ce.tokens_used), 0) as total_tokens_used
FROM chunks c
LEFT JOIN chunk_embeddings ce ON c.id = ce.chunk_id;
```

**Rationale:**
- View instead of table for real-time stats
- Only essential metrics tracked
- No historical tracking needed
- Simple aggregations for monitoring

## Access Patterns

### Primary Access Patterns
1. **Semantic Search**
   ```sql
   SELECT c.content, d.url, d.title
   FROM chunk_embeddings ce
   JOIN chunks c ON ce.chunk_id = c.id
   JOIN documents d ON c.document_id = d.id
   ORDER BY embedding <=> query_embedding
   LIMIT 5;
   ```

2. **URL Verification**
   ```sql
   SELECT id, title FROM documents WHERE url = 'specific_url';
   ```

3. **Document Reconstruction**
   ```sql
   SELECT content FROM chunks 
   WHERE document_id = ? 
   ORDER BY chunk_index;
   ```

4. **Unprocessed URLs**
   ```sql
    SELECT url FROM urls WHERE is_processed = FALSE;
   ```


## Future Considerations

1. **Scalability**
   - Schema supports horizontal scaling
   - No temporal dependencies
   - Clean separation of concerns

2. **Maintenance**
   - Minimal indexes to maintain
   - No complex constraints
   - Simple backup/restore

3. **Expandability**
   - Can add metadata later if needed
   - URLs table supports multiple data sources.
   - Model version tracking built-in
   - Support for multiple embedding models