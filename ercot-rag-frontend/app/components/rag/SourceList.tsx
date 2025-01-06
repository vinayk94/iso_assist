'use client';

import { BookOpen } from 'lucide-react';
import type { Source } from '../../lib/types';

interface SourceListProps {
    sources: Source[];
}

export default function SourceList({ sources }: SourceListProps) {
    const cleanExcerpt = (excerpt: string): string => {
        return excerpt.replace(/\b(\w+)\s+\1+\b/g, '$1'); // Remove duplicates
    };

    return (
        <div className="mt-8" id="sources">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
                <BookOpen size={20} className="mr-2" />
                Sources Used ({sources.length})
            </h2>
            
            <div className="space-y-4">
                {sources.map((source, idx) => (
                    <div
                        key={idx}
                        id={`source-${source.metadata.document_id}`}
                        className="bg-white rounded-lg shadow-sm p-4 border border-gray-200
                                 scroll-mt-8 transition-all duration-200"
                    >
                        <div className="flex justify-between items-start">
                            <div>
                                <h3 className="text-sm font-medium text-gray-900">
                                    {source.metadata.title}
                                </h3>
                                <span className="text-xs text-gray-500">
                                    {source.metadata.type}
                                </span>
                            </div>
                            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                                {Math.round(source.relevance * 100)}% match
                            </span>
                        </div>

                        {source.highlights[0] && (
                            <p className="mt-2 text-sm text-gray-600">
                                {cleanExcerpt(source.highlights[0])}
                            </p>
                        )}

                        {source.metadata.url && (
                            <a
                                href={source.metadata.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="mt-2 inline-flex items-center text-xs text-blue-600 hover:text-blue-800"
                            >
                                View Source
                            </a>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
