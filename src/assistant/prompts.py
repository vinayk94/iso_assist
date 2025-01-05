def create_rag_prompt(query: str, sources: List[Dict]) -> str:
    """Create enhanced prompt for better formatting"""
    source_text = []
    
    for source in sources:
        # Format source with title and relevant excerpts
        source_text.append(f"""
[{source['metadata']['title']}]:
{source['content']}
""".strip())
    
    return f"""You are an expert assistant for ERCOT documentation. Answer the following question using ONLY the provided sources.

Question: {query}

Guidelines:
1. Start with a direct, clear answer
2. Use numbered lists for steps or processes
3. Format important terms in **bold**
4. Always cite sources using [Document Title] format
5. Organize information logically
6. Be concise but comprehensive

Sources:
{chr(10).join(source_text)}

Answer the question step by step, using proper formatting and citations:"""