'use client';

import { ExternalLink, Clock, FileText } from 'lucide-react';
import type { Source } from '../../lib/types';

interface SourceCardProps {
    source: Source;
}

function cleanExcerpt(excerpt: string): string {
    // Remove repetitive text
    const cleaned = excerpt.replace(/(?:ERCOT\s*)+/g, 'ERCOT');
    // Ensure reasonable length
    return cleaned.length > 150 ? cleaned.slice(0, 150) + '...' : cleaned;
}


export default function SourceCard({ source }: SourceCardProps) {

    const excerpt = source.highlights?.[0] 
    ? cleanExcerpt(source.highlights[0])
    : null;

    // Only show URL button if it's a valid web URL
    const isValidUrl = source.metadata.url && (
        source.metadata.url.startsWith('http://') || 
        source.metadata.url.startsWith('https://')
    );

    return (
        <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
            <div className="flex justify-between items-start">
                <h3 className="text-sm font-medium text-gray-900">
                    {source.metadata.title}
                </h3>
                <span className="text-xs text-gray-500">
                        {source.metadata.type} {/* Add back the type label */}
                    </span>
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                    {Math.round(source.relevance * 100)}% match
                </span>
            </div>
            
            {excerpt && (
                <p className="mt-2 text-sm text-gray-600">
                    {excerpt}
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
                    <ExternalLink size={12} className="ml-1" />
                </a>
            )}
        </div>
    );
}