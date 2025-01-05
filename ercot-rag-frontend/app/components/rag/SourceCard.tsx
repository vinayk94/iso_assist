'use client';

import { ExternalLink, Clock, FileText } from 'lucide-react';
import type { Source } from '../../lib/types';

interface SourceCardProps {
    source: Source;
}

export default function SourceCard({ source }: SourceCardProps) {
    // Only show URL button if it's a valid web URL
    const isValidUrl = source.metadata.url && (
        source.metadata.url.startsWith('http://') || 
        source.metadata.url.startsWith('https://')
    );

    return (
        <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-2">
                <div className="flex items-start gap-2">
                    <FileText className="w-4 h-4 mt-1 text-gray-500" />
                    <div>
                        <h3 className="font-medium text-lg">
                            {source.metadata.title}
                        </h3>
                        <p className="text-sm text-gray-500">
                            {source.metadata.type === 'web' ? 'Web Page' : 'Document'}
                        </p>
                    </div>
                </div>
                <span className="text-sm bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
                    {Math.round(source.relevance * 100)}% match
                </span>
            </div>
            
            {source.highlights?.length > 0 && (
                <div className="mt-4 space-y-2">
                    <p className="text-sm font-medium text-gray-700">
                        Key Excerpts:
                    </p>
                    {source.highlights.map((highlight, idx) => (
                        <blockquote 
                            key={idx} 
                            className="text-sm text-gray-600 pl-3 border-l-2 border-gray-200"
                        >
                            {highlight}
                        </blockquote>
                    ))}
                </div>
            )}
            
            <div className="flex justify-between items-center mt-4">
                {isValidUrl ? (
                    <a
                        href={source.metadata.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-sm text-blue-600 
                                 hover:text-blue-800 hover:underline"
                    >
                        <ExternalLink size={14} />
                        View Source
                    </a>
                ) : (
                    <span className="text-sm text-gray-500 italic">
                        Source document
                    </span>
                )}
                
                {source.metadata.created_at && (
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                        <Clock size={12} />
                        {new Date(source.metadata.created_at).toLocaleDateString()}
                    </span>
                )}
            </div>
        </div>
    );
}