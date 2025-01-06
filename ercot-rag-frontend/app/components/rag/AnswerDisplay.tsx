'use client';

import React from 'react';
import { Clock } from 'lucide-react';
import SourceList from './SourceList';
import type { Source, QueryMetadata, Citation } from '../../lib/types';

interface AnswerDisplayProps {
    answer: string;
    sources: Source[];
    metadata: QueryMetadata | undefined; // Handle undefined metadata
    citations: Citation[];
}

const formatAnswerContent = (html: string) => {
    // Step 1: Remove colons after bold headings
    html = html.replace(/(<strong>[^:]*?)\s*:<\/strong>/g, '$1</strong>'); // Remove colon after bold text
    html = html.replace(/<\/li>\s*:/g, '</li>'); // Remove colon after list item

    // Step 2: Avoid nested wrapping for numbered lists
    html = html.replace(/(?<!<\/ol>)\s*(\d+)\.\s+(<strong>.*?<\/strong>)/g, '<li>$1. $2</li>'); // Convert numbered items to <li>
    html = html.replace(/(?<!<ol>)((?:<li>.*?<\/li>\s*)+)/g, '<ol>$1</ol>'); // Wrap <li> elements in <ol> only if not already inside one

    // Step 3: Ensure proper paragraph tags
    html = html.replace(/\n\n+/g, '</p><p>'); // Convert double line breaks into paragraph breaks
    html = html.replace(/\n/g, ' '); // Replace single line breaks with spaces

    // Step 4: Ensure HTML starts and ends with <p>
    if (!html.startsWith('<p>')) {
        html = `<p>${html}`;
    }
    if (!html.endsWith('</p>')) {
        html += '</p>';
    }

    return html.trim();
};







export default function AnswerDisplay({
    answer,
    sources,
    metadata,
}: AnswerDisplayProps) {
    const processingTime = metadata?.processing_time
        ? `${Number(metadata.processing_time).toFixed(2)}s`
        : 'Processing...';
    const chunkMessage = metadata?.total_chunks
        ? `Found ${metadata.total_chunks} relevant chunks from ${metadata.unique_sources} sources.`
        : 'No relevant chunks found. The answer was generated using general knowledge from verified sources.';

    // Handle clicks on citations (<cite>)
    const handleCitationClick = (e: React.MouseEvent<HTMLDivElement>) => {
        const target = e.target as HTMLElement;
        if (target.tagName === 'CITE') {
            const sourceId = target.getAttribute('data-source-id');
            if (sourceId) {
                const sourceElement = document.getElementById(sourceId);
                if (sourceElement) {
                    sourceElement.scrollIntoView({ behavior: 'smooth' });
                } else {
                    console.warn(`No source found with ID: ${sourceId}`);
                }
            }
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto">
            {/* Answer Section */}
            <div className="bg-white rounded-lg shadow-sm p-6 mb-4">
                <h2 className="font-bold text-xl mb-4">Answer</h2>
                <div
                    className="answer-content text-gray-800"
                    dangerouslySetInnerHTML={{ __html: formatAnswerContent(answer) }}
                    onClick={(e) => {
                        const target = e.target as HTMLElement;
                        if (target.tagName === 'CITE') {
                            const sourceId = target.getAttribute('data-source-id');
                            if (sourceId) {
                                const sourceElement = document.getElementById(`source-${sourceId}`);
                                if (sourceElement) {
                                    sourceElement.scrollIntoView({ behavior: 'smooth' });
                                } else {
                                    console.warn(`No source found with ID: ${sourceId}`);
                                }
                            }
                        }
                    }}
                />


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
                    <h2 className="font-bold text-xl mb-4">Sources Used</h2>
                    <SourceList sources={sources} />
                </>
            )}
        </div>
    );
}
