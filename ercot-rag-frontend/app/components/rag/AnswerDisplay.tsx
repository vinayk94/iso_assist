'use client';

import React from 'react';
import { Clock } from 'lucide-react';
import CitationMarker from './CitationMarker';
import SourceList from './SourceList';
import type { Citation, Source } from '../../lib/types';

interface Segment {
    type: 'text' | 'citation';
    content: string;
    source?: Source;
}

interface AnswerDisplayProps {
    answer: string;
    citations: Citation[];
    sources: Source[];
    processingTime: number;
}

export default function AnswerDisplay({ 
    answer, 
    citations, 
    sources, 
    processingTime 
}: AnswerDisplayProps) {
    // Create segments with citations
    const segments: Segment[] = [];
    let lastIndex = 0;

    // Sort citations by position
    const sortedCitations = [...citations].sort((a, b) => a.start_idx - b.start_idx);

    sortedCitations.forEach(citation => {
        // Add text before citation
        if (citation.start_idx > lastIndex) {
            segments.push({
                type: 'text',
                content: answer.slice(lastIndex, citation.start_idx)
            });
        }

        // Find corresponding source
        const source = sources.find(s => s.title === citation.title);

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

    const scrollToSources = () => {
        document.getElementById('sources')?.scrollIntoView({ 
            behavior: 'smooth' 
        });
    };

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
                                    onSourceClick={scrollToSources}
                                />
                            )}
                        </React.Fragment>
                    ))}
                </div>

                {/* Processing time */}
                <div className="mt-4 flex items-center text-sm text-gray-500">
                    <Clock size={14} className="mr-1" />
                    <span>
                        Processed in {processingTime.toFixed(2)}s using {sources.length} sources
                    </span>
                </div>
            </div>

            {/* Sources Section */}
            <SourceList sources={sources} />
        </div>
    );
}