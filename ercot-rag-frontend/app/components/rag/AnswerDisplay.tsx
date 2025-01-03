'use client';

import React from 'react';
import { ExternalLink, Clock } from 'lucide-react';
import type { Citation, Source } from '../../lib/types';

interface AnswerDisplayProps {
    answer: string;
    citations: Citation[];
    sources: Source[];
    processingTime: number;
}

// Add this interface at the top of AnswerDisplay.tsx
interface Segment {
    type: 'text' | 'citation';
    content: string;
    source?: Source;  // Make source optional since text segments won't have it
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

        // Add citation
        segments.push({
            type: 'citation',
            content: citation.title,
            source: sources.find(s => s.title === citation.title)
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
                                <button
                                    onClick={() => {
                                        document.getElementById('sources')?.scrollIntoView({ 
                                            behavior: 'smooth' 
                                        });
                                    }}
                                    className="inline-flex items-center px-2 py-0.5 mx-1 rounded 
                                             bg-blue-50 text-blue-700 hover:bg-blue-100 
                                             transition-colors"
                                >
                                    [{segment.content}]
                                    {segment.source?.url && (
                                        <ExternalLink size={12} className="ml-1" />
                                    )}
                                </button>
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
            <div id="sources" className="mt-8">
                <h2 className="text-xl font-semibold mb-4">Sources</h2>
                <div className="space-y-4">
                    {sources.map((source, idx) => (
                        <div 
                            key={idx}
                            className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                        >
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
                                    {source.highlights.map((highlight, hidx) => (
                                        <p 
                                            key={hidx} 
                                            className="text-sm text-gray-600 mb-1"
                                        >
                                            • {highlight}
                                        </p>
                                    ))}
                                </div>
                            )}
                            
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
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}