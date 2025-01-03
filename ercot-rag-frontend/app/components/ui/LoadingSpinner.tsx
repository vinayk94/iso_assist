// app/components/ui/LoadingSpinner.tsx
'use client';

import { Loader2 } from 'lucide-react';

export default function LoadingSpinner() {
    return (
        <div className="flex justify-center items-center">
            <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        </div>
    );
}

