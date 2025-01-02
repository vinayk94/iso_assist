import psycopg2
import tiktoken
import os
from dotenv import load_dotenv
import logging
from tqdm import tqdm
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Dict, Tuple, Set
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("chunk_optimizer.log"),
        logging.StreamHandler()
    ]
)

# Document type specific configurations
DOCUMENT_CONFIGS = {
    'technical': {
        'similarity_threshold': 0.98,
        'min_length': 20,
        'preserve_patterns': [
            r'Section \d+\.\d+',
            r'Resource\s+\w+',
            r'[A-Z]{2,}(?:\s+[A-Z]{2,})*',
            r'\d+\s*(?:MW|MVar|kV)',
            r'QSE\s+Comment:',
            r'Protocol\s+Section',
            r'Resource\s+ID:',
            r'(?:Primary|Secondary|Backup)\s+(?:Contact|Phone|Email)'
        ]
    },
    'legal': {
        'similarity_threshold': 0.95,
        'min_length': 50,
        'preserve_patterns': [
            r'Section \d+\.\d+',
            r'Article \w+',
            r'Exhibit [A-Z]',
            r'pursuant to',
            r'herein',
            r'shall|must|will'
        ]
    },
    'excel': {
        'similarity_threshold': 0.99,
        'min_length': 10,
        'preserve_patterns': [
            r'^(?!.*NaN).*$',
            r'^\s*[A-Za-z][A-Za-z\s_]+$',
            r'\d+(?:\.\d+)?(?:\s*(?:MW|MVar|kV|kW|V|A))',
            r'(?:Date|Time|ID|Name|Value|Status|Comment)'
        ]
    },
    'default': {
        'similarity_threshold': 0.97,
        'min_length': 35,
        'preserve_patterns': []
    }
}

def determine_document_type(file_name: str, content: str = "") -> str:
    """Enhanced document type detection"""
    technical_patterns = [
        r'checklist',
        r'commissioning',
        r'specification',
        r'protocol',
        r'resource',
        r'generator',
        r'technical',
        r'operational',
        r'export',
        r'meter',
        r'template',
        r'RIOO',
        r'ELSE',
        r'QSE',
        r'measurement',
        r'data'
    ]
    
    legal_patterns = [
        r'letter of credit',
        r'agreement',
        r'contract',
        r'legal',
        r'terms',
        r'conditions',
        r'rights',
        r'obligations',
        r'liability'
    ]
    
    # Check if it's an Excel file first
    if file_name.lower().endswith(('.xlsx', '.xls')):
        return 'excel'
    
    file_name_lower = file_name.lower()
    content_lower = content.lower()
    
    # Check technical patterns in both filename and content
    for pattern in technical_patterns:
        if re.search(pattern, file_name_lower) or re.search(pattern, content_lower):
            return 'technical'
    
    # Check legal patterns in both filename and content
    for pattern in legal_patterns:
        if re.search(pattern, file_name_lower) or re.search(pattern, content_lower):
            return 'legal'
    
    return 'default'

def is_nan_heavy(text: str) -> bool:
    """Check if text contains too many NaN values"""
    nan_count = text.lower().count('nan')
    words = text.split()
    return nan_count > len(words) * 0.3 if words else True

def is_header_row(text: str) -> bool:
    """Check if text appears to be a header row"""
    cleaned = re.sub(r'Unnamed:\s*\d+', '', text).strip()
    if not cleaned:
        return False
    
    header_patterns = [
        r'^[A-Za-z][A-Za-z\s_]+$',
        r'(?:ID|Name|Date|Time|Value|Status|Comments?)\b',
        r'^(?:Primary|Secondary|Backup|Contact|Phone|Email)\b'
    ]
    
    return any(re.search(pattern, cleaned) for pattern in header_patterns)

def is_valid_data_row(text: str) -> bool:
    """Check if text contains valid data"""
    cleaned = re.sub(r'\bNaN\b', '', text).strip()
    if not cleaned:
        return False
    return bool(re.search(r'[A-Za-z0-9]+', cleaned))

def is_low_quality_chunk(text: str, doc_type: str, file_name: str) -> bool:
    """Enhanced low quality detection with Excel handling"""
    if not text or not text.strip():
        return True
    
    text = ' '.join(text.split())
    config = DOCUMENT_CONFIGS[doc_type]
    
    # Check preservation patterns first
    for pattern in config['preserve_patterns']:
        if re.search(pattern, text):
            return False
    
    # Special handling for Excel files
    if doc_type == 'excel':
        if is_header_row(text):
            return False
        if is_nan_heavy(text) and not is_valid_data_row(text):
            return True
        if re.search(r'\d+(?:\.\d+)?(?:\s*(?:MW|MVar|kV|kW|V|A))', text):
            return False
    
    # Length check
    if len(text) < config['min_length']:
        return True
    
    # Check for mostly numbers or special characters
    alpha_ratio = sum(c.isalpha() for c in text) / len(text) if text else 0
    if alpha_ratio < 0.3 and not re.search(r'\d+\s*(?:MW|MVar|kV)', text):
        return True
    
    # Check for repetitive content
    words = text.split()
    if len(words) >= 4:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio < 0.5:
            return True
    
    return False

# Main Processing Functions

def create_backup(conn):
    """Create a backup of the chunks table"""
    cur = conn.cursor()
    try:
        cur.execute("DROP TABLE IF EXISTS chunks_backup")
        cur.execute("CREATE TABLE chunks_backup AS SELECT * FROM chunks;")
        conn.commit()
        logging.info("Created backup table: chunks_backup")
    finally:
        cur.close()

def analyze_chunks(conn) -> Tuple[List[Dict], Dict[str, int]]:
    """Analyze chunks with enhanced document type detection"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT c.id, c.content, c.document_id, d.file_name 
            FROM chunks c
            LEFT JOIN documents d ON c.document_id = d.id
        """)
        chunks = cur.fetchall()
        
        low_quality_chunks = []
        stats = {'technical': 0, 'legal': 0, 'excel': 0, 'default': 0}
        
        for chunk_id, content, doc_id, file_name in tqdm(chunks, desc="Analyzing chunks"):
            if not file_name:
                continue
            
            doc_type = determine_document_type(file_name, content)
            stats[doc_type] += 1
            
            if is_low_quality_chunk(content, doc_type, file_name):
                low_quality_chunks.append({
                    'id': chunk_id,
                    'text': content,
                    'document_id': doc_id,
                    'file_name': file_name,
                    'doc_type': doc_type
                })
        
        return low_quality_chunks, stats
    finally:
        cur.close()

def process_document_chunks(chunks: List[Tuple]) -> List[Dict]:
    """Process chunks from a single document with improved similarity detection"""
    if not chunks:
        return []
    
    doc_id = chunks[0][2]
    file_name = chunks[0][3]
    doc_type = determine_document_type(file_name)
    config = DOCUMENT_CONFIGS[doc_type]
    
    similar_pairs = []
    valid_chunks = []
    
    # Pre-filter chunks
    for chunk in chunks:
        content = chunk[1]
        if not is_low_quality_chunk(content, doc_type, file_name):
            valid_chunks.append(chunk)
    
    if len(valid_chunks) < 2:
        return []
    
    chunk_texts = [c[1] for c in valid_chunks]
    
    vectorizer = TfidfVectorizer(stop_words='english')
    try:
        tfidf_matrix = vectorizer.fit_transform(chunk_texts)
        similarities = cosine_similarity(tfidf_matrix)
        
        for i in range(len(chunk_texts)):
            for j in range(i + 1, len(chunk_texts)):
                if similarities[i][j] > config['similarity_threshold']:
                    # Skip if either chunk should be preserved
                    if doc_type in ['technical', 'excel']:
                        if any(should_preserve_chunk(text, doc_type) 
                              for text in [chunk_texts[i], chunk_texts[j]]):
                            continue
                    
                    similar_pairs.append({
                        'id1': valid_chunks[i][0],
                        'text1': chunk_texts[i],
                        'id2': valid_chunks[j][0],
                        'text2': chunk_texts[j],
                        'document_id': doc_id,
                        'file_name': file_name,
                        'similarity': similarities[i][j],
                        'doc_type': doc_type
                    })
    
    except Exception as e:
        logging.warning(f"Error processing document {doc_id}: {e}")
    
    return similar_pairs

def find_similar_chunks(conn) -> List[Dict]:
    """Find similar chunks with improved comparison logic"""
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT c.id, c.content, c.document_id, d.file_name 
            FROM chunks c
            LEFT JOIN documents d ON c.document_id = d.id
            ORDER BY d.id, c.id
        """)
        chunks = cur.fetchall()
        
        similar_pairs = []
        current_doc_chunks = []
        current_doc_id = None
        
        for chunk in tqdm(chunks, desc="Finding similar chunks"):
            chunk_id, content, doc_id, file_name = chunk
            
            if not file_name:
                continue
            
            if doc_id != current_doc_id:
                if current_doc_chunks:
                    pairs = process_document_chunks(current_doc_chunks)
                    similar_pairs.extend(pairs)
                current_doc_chunks = []
                current_doc_id = doc_id
            
            current_doc_chunks.append(chunk)
        
        if current_doc_chunks:
            pairs = process_document_chunks(current_doc_chunks)
            similar_pairs.extend(pairs)
        
        return similar_pairs
    finally:
        cur.close()

def should_preserve_chunk(text: str, doc_type: str) -> bool:
    """Check if chunk should be preserved based on document type rules"""
    config = DOCUMENT_CONFIGS[doc_type]
    return any(re.search(pattern, text) for pattern in config['preserve_patterns'])

def remove_chunks(conn, chunk_ids: List[int]) -> int:
    """Remove specified chunks from database"""
    if not chunk_ids:
        return 0
    
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM chunks WHERE id = ANY(%s) RETURNING id",
            (chunk_ids,)
        )
        removed = cur.fetchall()
        conn.commit()
        return len(removed)
    finally:
        cur.close()

def print_chunk_info(chunk: Dict, prefix: str = ""):
    """Pretty print chunk information"""
    print(f"{prefix}Chunk ID: {chunk['id']}")
    print(f"{prefix}Document: {chunk['file_name']}")
    print(f"{prefix}Type: {chunk.get('doc_type', 'Unknown')}")
    text_preview = chunk['text'][:150] + "..." if len(chunk['text']) > 150 else chunk['text']
    print(f"{prefix}Text: {text_preview}")
    print()

def optimize_chunks(postgres_uri: str):
    """Main optimization function with improved handling"""
    conn = psycopg2.connect(postgres_uri)
    
    try:
        print("\nAnalyzing Database Chunks...")
        print("-" * 50)
        
        create_backup(conn)
        
        print("\n1. Analyzing chunks by document type...")
        low_quality_chunks, stats = analyze_chunks(conn)
        
        print("\nDocument type statistics:")
        for doc_type, count in sorted(stats.items()):
            print(f"  {doc_type.capitalize()}: {count} chunks")
        
        print(f"\nFound {len(low_quality_chunks)} low quality chunks")
        if low_quality_chunks:
            print("\nExample low quality chunks by document type:")
            examples_by_type = {}
            for chunk in low_quality_chunks[:15]:  # Show up to 15 examples
                doc_type = chunk['doc_type']
                if doc_type not in examples_by_type:
                    examples_by_type[doc_type] = []
                if len(examples_by_type[doc_type]) < 3:  # Up to 3 examples per type
                    examples_by_type[doc_type].append(chunk)
            
            for doc_type, examples in sorted(examples_by_type.items()):
                print(f"\n{doc_type.capitalize()} documents:")
                for example in examples:
                    print_chunk_info(example, prefix="  ")
        
        print("\n2. Finding similar chunks...")
        similar_pairs = find_similar_chunks(conn)
        print(f"\nFound {len(similar_pairs)} similar chunk pairs")
        
        if similar_pairs:
            print("\nExample similar pairs by document type:")
            examples_by_type = {}
            for pair in similar_pairs[:15]:  # Show up to 15 pairs
                doc_type = pair['doc_type']
                if doc_type not in examples_by_type:
                    examples_by_type[doc_type] = []
                if len(examples_by_type[doc_type]) < 2:  # Up to 2 pairs per type
                    examples_by_type[doc_type].append(pair)
            
            for doc_type, examples in sorted(examples_by_type.items()):
                print(f"\n{doc_type.capitalize()} documents:")
                for pair in examples:
                    print(f"Similarity: {pair['similarity']:.2f}")
                    print("Chunk 1:")
                    print_chunk_info({
                        'id': pair['id1'],
                        'text': pair['text1'],
                        'file_name': pair['file_name'],
                        'doc_type': pair['doc_type']
                    }, prefix="  ")
                    print("Chunk 2:")
                    print_chunk_info({
                        'id': pair['id2'],
                        'text': pair['text2'],
                        'file_name': pair['file_name'],
                        'doc_type': pair['doc_type']
                    }, prefix="  ")
        
        # Calculate potential savings
        enc = tiktoken.get_encoding("cl100k_base")
        tokens_from_low_quality = sum(
            len(enc.encode(chunk['text'])) 
            for chunk in low_quality_chunks
        )
        tokens_from_similar = sum(
            len(enc.encode(pair['text2'])) 
            for pair in similar_pairs
        )
        
        # Summary
        print("\nSummary of Proposed Changes:")
        print("-" * 50)
        print("By document type:")
        doc_type_counts = {
            'technical': {'low': 0, 'similar': 0},
            'legal': {'low': 0, 'similar': 0},
            'excel': {'low': 0, 'similar': 0},
            'default': {'low': 0, 'similar': 0}
        }
        
        for chunk in low_quality_chunks:
            doc_type_counts[chunk['doc_type']]['low'] += 1
        for pair in similar_pairs:
            doc_type_counts[pair['doc_type']]['similar'] += 1
            
        for doc_type, counts in sorted(doc_type_counts.items()):
            print(f"\n{doc_type.capitalize()}:")
            print(f"  Low quality chunks: {counts['low']}")
            print(f"  Similar pairs: {counts['similar']}")
        
        print(f"\nTotal low quality chunks: {len(low_quality_chunks)}")
        print(f"Total similar pairs: {len(similar_pairs)}")
        print(f"Estimated tokens to be saved: {tokens_from_low_quality + tokens_from_similar:,}")
        print("\nA backup has been created as 'chunks_backup'")
        
        # Get confirmation
        confirm = input("\nWould you like to proceed with optimization? (yes/no): ")
        
        if confirm.lower() == 'yes':
            # Remove low quality chunks
            if low_quality_chunks:
                removed = remove_chunks(conn, [c['id'] for c in low_quality_chunks])
                print(f"Removed {removed} low quality chunks")
            
            # Remove similar chunks (keeping first of each pair)
            if similar_pairs:
                to_remove = [pair['id2'] for pair in similar_pairs]
                removed = remove_chunks(conn, to_remove)
                print(f"Removed {removed} similar chunks")
                
            print("\nOptimization complete!")
            print("\nTo restore from backup if needed, run restore_chunks.py")
        else:
            print("\nOperation cancelled. No changes made to the database.")
            print("The backup table 'chunks_backup' has been retained.")
            
    except Exception as e:
        logging.error(f"Error during optimization: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    load_dotenv()
    postgres_uri = os.getenv("POSTGRESQL_URI")
    
    if not postgres_uri:
        logging.error("PostgreSQL URI not found in environment variables")
        sys.exit(1)
        
    optimize_chunks(postgres_uri)