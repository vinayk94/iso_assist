// app/lib/api.ts
import type { RAGResponse } from './types';

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function queryRAG(query: string): Promise<RAGResponse> {
    const response = await fetch(`${API_URL}/api/query`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
    });

    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }

    const data = await response.json();
    return {
        query,  // Add the original query
        ...data
    };
}