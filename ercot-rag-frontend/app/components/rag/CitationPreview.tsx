// app/components/rag/CitationPreview.tsx
'use client';

import { BookOpen, Clock } from 'lucide-react';
import type { Source } from '../../lib/types';

interface CitationPreviewProps {
    source: Source;
}

export default function CitationPreview({ source }: CitationPreviewProps) {
    return (
        <div className="w-80 bg-white rounded-lg shadow-lg p-4 border border-gray-200">
            <div className="flex items-start justify-between mb-2">
                <h4 className="font-medium text-sm flex items-center">
                    <BookOpen size={14} className="mr-2" />
                    {source.title}
                </h4>
                <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                    {Math.round(source.relevance * 100)}% match
                </span>
            </div>

            {source.highlights.length > 0 && (
                <div className="mt-2">
                    <p className="text-xs text-gray-600 line-clamp-3">
                        {source.highlights[0]}
                    </p>
                </div>
            )}

            {source.metadata.last_updated && (
                <div className="mt-2 flex items-center text-xs text-gray-500">
                    <Clock size={12} className="mr-1" />
                    Updated: {new Date(source.metadata.last_updated).toLocaleDateString()}
                </div>
            )}
        </div>
    );
}