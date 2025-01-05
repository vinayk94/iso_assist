'use client';

import { ExternalLink } from 'lucide-react';
import type { Source } from '../../lib/types';

interface CitationMarkerProps {
    title: string;
    source?: Source;
    onSourceClick: () => void;
}

export default function CitationMarker({ 
    title, 
    source, 
    onSourceClick 
}: CitationMarkerProps) {
    const handleClick = (e: React.MouseEvent) => {
        e.preventDefault();
        onSourceClick();
    };

    if (!source) {
        return (
            <span className="text-gray-400">
                [{title}]
            </span>
        );
    }

    return (
        <button
            onClick={handleClick}
            className="inline-flex items-center px-2 py-0.5 mx-1 rounded 
                     bg-blue-50 text-blue-700 hover:bg-blue-100 
                     transition-colors group relative"
        >
            [{title}]
            {source.metadata.url && (
                <a
                    href={source.metadata.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="ml-1 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                    <ExternalLink size={12} />
                </a>
            )}
            
            {/* Tooltip preview */}
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 
                          opacity-0 pointer-events-none group-hover:opacity-100 
                          transition-opacity z-10 w-64 bg-white p-3 rounded-lg shadow-lg
                          text-left">
                <p className="text-xs font-medium text-gray-900 mb-1">
                    {source.metadata.title}
                </p>
                {source.highlights[0] && (
                    <p className="text-xs text-gray-600">
                        {source.highlights[0]}
                    </p>
                )}
            </div>
        </button>
    );
}