'use client';

import { ExternalLink } from 'lucide-react';
import type { Source } from '../../lib/types';
import CitationPreview from './CitationPreview';

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
    return (
        <div className="relative inline-block group">
            <button
                onClick={onSourceClick}
                className="inline-flex items-center px-2 py-0.5 mx-1 rounded 
                         bg-blue-50 text-blue-700 hover:bg-blue-100 
                         transition-colors"
            >
                [{title}]
                {source?.url && (
                    <ExternalLink 
                        size={12} 
                        className="ml-1 opacity-0 group-hover:opacity-100 transition-opacity" 
                    />
                )}
            </button>

            {/* Preview popup */}
            {source && (
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 
                              opacity-0 pointer-events-none
                              group-hover:opacity-100 group-hover:pointer-events-auto
                              transition-opacity duration-200 z-10">
                    <CitationPreview source={source} />
                </div>
            )}
        </div>
    );
}