// app/components/ui/ErrorMessage.tsx
'use client';

import { AlertCircle } from 'lucide-react';

interface ErrorMessageProps {
    message: string;
    retry?: () => void;
}

export default function ErrorMessage({ message, retry }: ErrorMessageProps) {
    return (
        <div className="w-full max-w-3xl mx-auto">
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start">
                    <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 mr-3" />
                    <div>
                        <h3 className="text-red-800 font-medium">
                            Error Occurred
                        </h3>
                        <p className="text-red-700 mt-1">
                            {message}
                        </p>
                        {retry && (
                            <button
                                onClick={retry}
                                className="mt-3 text-sm text-red-600 hover:text-red-800 
                                         underline focus:outline-none"
                            >
                                Try Again
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}