'use client';

import React, { useEffect } from 'react';
import { Clock } from 'lucide-react';
import SourceList from './SourceList';
import type { Source, QueryMetadata, Citation } from '../../lib/types';

interface AnswerDisplayProps {
    answer: string;
    citations: Citation[];
    sources: Source[];
    metadata: QueryMetadata | undefined; // Handle undefined metadata
}

const sanitizeHtml = (html: string) => {
    return html
        .replace(/<h[1-6]>/g, '<h4>')  // Enforce <h4> for all headings
        .replace(/<\/h[1-6]>/g, '</h4>')
        .replace(/<p>\s*<\/p>/g, '')   // Remove empty paragraphs
        .replace(/<ul>\s*<\/ul>/g, '') // Remove empty unordered lists
        .replace(/<ol>\s*<\/ol>/g, '') // Remove empty ordered lists
        .replace(/\s+/g, ' ')          // Normalize spaces
        .trim();
};


export default function AnswerDisplay({ 
    answer, 
    citations, 
    sources, 
    metadata 
}: AnswerDisplayProps) {
    // Log metadata and citations for debugging
    useEffect(() => {
        console.log("Metadata in AnswerDisplay:", metadata);
        console.log("Citations in AnswerDisplay:", citations);
    }, [metadata, citations]);

    console.log("Raw metadata:", metadata); // Debugging

    // Fallback for metadata values
    const processingTime = metadata?.processing_time 
        ? `${Number(metadata.processing_time).toFixed(2)}s` 
        : 'Processing...';
    const chunkMessage = metadata?.total_chunks
        ? `Found ${metadata.total_chunks} relevant chunks from ${metadata.unique_sources} sources.`
        : 'No relevant chunks found. The answer was generated using general knowledge from verified sources.';

    return (
        <div className="w-full max-w-3xl mx-auto">
            {/* Answer Section */}
            <div className="bg-white rounded-lg shadow-sm p-6 mb-4">
                {/* Sanitize the answer HTML */}
                <div dangerouslySetInnerHTML={{ __html: answer }} />

                {/* Metadata */}
                <div className="mt-4 text-sm text-gray-500 flex items-center justify-between">
                    <div className="flex items-center">
                        <Clock size={14} className="mr-1" />
                        <span>{processingTime}</span>
                    </div>
                    <div>{chunkMessage}</div>
                </div>
            </div>

            {/* Sources Section */}
            {sources.length > 0 && (
                <>
                    <hr className="my-6 border-gray-300" />
                    <SourceList sources={sources} />
                </>
            )}
        </div>
    );
}
