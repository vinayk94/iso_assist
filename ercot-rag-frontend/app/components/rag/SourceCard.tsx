'use client';

import { ExternalLink, Clock } from 'lucide-react';
import type { Source } from '../../lib/types';

interface SourceCardProps {
    source: Source;
}

export default function SourceCard({ source }: SourceCardProps) {
    return (
        <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-2">
                <h3 className="font-medium text-lg">{source.title}</h3>
                <span className="text-sm text-gray-500">
                    Relevance: {Math.round(source.relevance * 100)}%
                </span>
            </div>
            
            {source.highlights.length > 0 && (
                <div className="mb-2">
                    <p className="text-sm font-medium text-gray-700 mb-1">
                        Key Excerpts:
                    </p>
                    {source.highlights.map((highlight, idx) => (
                        <p 
                            key={idx} 
                            className="text-sm text-gray-600 mb-1 pl-4 border-l-2 border-gray-200"
                        >
                            {highlight}
                        </p>
                    ))}
                </div>
            )}
            
            <div className="flex justify-between items-center mt-2">
                {source.url && (
                    <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center text-sm text-blue-600 
                                 hover:text-blue-800"
                    >
                        View Source <ExternalLink size={14} className="ml-1" />
                    </a>
                )}
                
                {source.metadata.last_updated && (
                    <span className="text-xs text-gray-500 flex items-center">
                        <Clock size={12} className="mr-1" />
                        Updated: {new Date(source.metadata.last_updated).toLocaleDateString()}
                    </span>
                )}
            </div>
        </div>
    );
}