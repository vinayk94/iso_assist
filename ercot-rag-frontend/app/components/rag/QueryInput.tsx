'use client';  // This is needed for client-side interactivity

import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface QueryInputProps {
    onSubmit: (query: string) => void;
    isLoading: boolean;
    defaultValue?: string;  // Make it optional
}

export default function QueryInput({ onSubmit, isLoading, 
    defaultValue = ''  }: QueryInputProps) {
    const [query, setQuery] = useState(defaultValue);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (query.trim() && !isLoading) {
            onSubmit(query.trim());
        }
    };

    return (
        <form onSubmit={handleSubmit} className="w-full max-w-3xl mx-auto">
            <div className="relative">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Ask about ERCOT registration processes..."
                    className="w-full p-4 pr-12 rounded-lg border border-gray-300 shadow-sm 
                             focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                             disabled:bg-gray-50 disabled:cursor-not-allowed"
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    disabled={isLoading || !query.trim()}
                    className="absolute right-3 top-1/2 -translate-y-1/2
                             text-gray-500 hover:text-gray-700 
                             disabled:text-gray-300 disabled:cursor-not-allowed"
                    aria-label={isLoading ? "Loading..." : "Search"}
                >
                    {isLoading ? (
                        <Loader2 className="w-6 h-6 animate-spin" />
                    ) : (
                        <Search className="w-6 h-6" />
                    )}
                </button>
            </div>
        </form>
    );
}