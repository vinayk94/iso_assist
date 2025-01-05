'use client';

import React from 'react';
import { Clock } from 'lucide-react';
import CitationMarker from './CitationMarker';
import SourceList from './SourceList';
import type { Citation, Source, QueryMetadata } from '../../lib/types';

interface AnswerDisplayProps {
    answer: string;
    citations: Citation[];
    sources: Source[];
    metadata: QueryMetadata;
}

interface Segment {
    type: 'text' | 'citation';
    content: string;
    source?: Source;
}

export default function AnswerDisplay({ 
    answer, 
    citations, 
    sources, 
    metadata 
}: AnswerDisplayProps) {
    // Handle case where metadata might be undefined
    const processingTime = metadata?.processing_time ?? 0;
    const totalChunks = metadata?.total_chunks ?? 0;
    const uniqueSources = metadata?.unique_sources ?? 0;

    // Create segments with citations
    const segments: Segment[] = [];
    let lastIndex = 0;

    // Sort citations by position
    const sortedCitations = [...(citations || [])].sort((a, b) => a.start_idx - b.start_idx);

    sortedCitations.forEach(citation => {
        // Add text before citation
        if (citation.start_idx > lastIndex) {
            segments.push({
                type: 'text',
                content: answer.slice(lastIndex, citation.start_idx)
            });
        }

        // Find corresponding source
        const source = sources.find(s => s.metadata.title === citation.title);

        // Add citation
        segments.push({
            type: 'citation',
            content: citation.title,
            source
        });

        lastIndex = citation.end_idx;
    });

    // Add remaining text
    if (lastIndex < answer.length) {
        segments.push({
            type: 'text',
            content: answer.slice(lastIndex)
        });
    }

    return (
        <div className="w-full max-w-3xl mx-auto">
            <div className="bg-white rounded-lg shadow-sm p-6 mb-4">
                {/* Answer with citations */}
                <div className="prose max-w-none">
                    {segments.map((segment, idx) => (
                        <React.Fragment key={idx}>
                            {segment.type === 'text' ? (
                                <span>{segment.content}</span>
                            ) : (
                                <CitationMarker
                                    title={segment.content}
                                    source={segment.source}
                                    onSourceClick={() => {
                                        document.getElementById('sources')?.scrollIntoView({ 
                                            behavior: 'smooth' 
                                        });
                                    }}
                                />
                            )}
                        </React.Fragment>
                    ))}
                </div>

                {/* Processing metadata */}
                <div className="mt-4 flex items-center justify-between text-sm text-gray-500">
                    <div className="flex items-center">
                        <Clock size={14} className="mr-1" />
                        <span>
                            Processed in {processingTime.toFixed(2)}s
                        </span>
                    </div>
                    <div>
                        Found {totalChunks} relevant chunks from {uniqueSources} sources
                    </div>
                </div>
            </div>

            {/* Sources Section */}
            {sources.length > 0 && <SourceList sources={sources} />}
        </div>
    );
}