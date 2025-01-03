'use client';

import { BookOpen } from 'lucide-react';
import SourceCard from './SourceCard';
import type { Source } from '../../lib/types';

interface SourceListProps {
    sources: Source[];
}

export default function SourceList({ sources }: SourceListProps) {
    return (
        <div id="sources" className="mt-8">
            <h2 className="text-xl font-semibold mb-4 flex items-center">
                <BookOpen size={20} className="mr-2" />
                Sources Used ({sources.length})
            </h2>
            
            {sources.length > 0 ? (
                <div className="space-y-4">
                    {sources.map((source, idx) => (
                        <SourceCard key={idx} source={source} />
                    ))}
                </div>
            ) : (
                <p className="text-gray-500 italic">
                    No sources available for this response.
                </p>
            )}
        </div>
    );
}