'use client';

import { useState } from 'react';
import QueryInput from './components/rag/QueryInput';
import AnswerDisplay from './components/rag/AnswerDisplay';
import LoadingAnswer from './components/ui/LoadingAnswer';
import ErrorMessage from './components/ui/ErrorMessage';
import type { RAGResponse } from './lib/types';

export default function Home() {
    const [isLoading, setIsLoading] = useState(false);
    const [response, setResponse] = useState<RAGResponse | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [currentQuery, setCurrentQuery] = useState<string>('');  // Track current query

    const handleQuery = async (query: string) => {
        setIsLoading(true);
        setError(null);
        setCurrentQuery(query);  // Save current query for retry
        
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query }),
            });
            
            if (!res.ok) {
                throw new Error('Failed to get response');
            }
            
            const data: RAGResponse = await res.json();
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            setResponse(data);
            
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Something went wrong');
        } finally {
            setIsLoading(false);
        }
    };

    const retry = () => {
        if (currentQuery) {
            handleQuery(currentQuery);
        }
    };

    return (
        <main className="min-h-screen p-6 bg-gray-50">
            <div className="max-w-4xl mx-auto">
                <h1 className="text-3xl font-bold text-center mb-8">
                    ERCOT Documentation Assistant
                </h1>

                <QueryInput 
                    onSubmit={handleQuery} 
                    isLoading={isLoading}
                    defaultValue={currentQuery}  // Optional: preserve query
                />

                {error && (
                    <div className="mt-6">
                        <ErrorMessage 
                            message={error} 
                            retry={currentQuery ? retry : undefined} 
                        />
                    </div>
                )}

                {isLoading && (
                    <div className="mt-8">
                        <LoadingAnswer />
                    </div>
                )}

                {response && !isLoading && (
                    <div className="mt-8">
                        <AnswerDisplay 
                            answer={response.answer}
                            citations={response.citations} // Pass citations
                            sources={response.sources}
                            metadata={response.metadata}
                        />
                    </div>
                )}
            </div>
        </main>
    );
}
