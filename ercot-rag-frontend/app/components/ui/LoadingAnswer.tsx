'use client';

export default function LoadingAnswer() {
    return (
        <div className="w-full max-w-3xl mx-auto animate-pulse">
            <div className="bg-white rounded-lg shadow-sm p-6">
                {/* Fake text lines */}
                <div className="space-y-4">
                    <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                    <div className="h-4 bg-gray-200 rounded w-full"></div>
                    <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                    <div className="h-4 bg-gray-200 rounded w-4/5"></div>
                </div>

                {/* Fake citations */}
                <div className="mt-4 flex gap-2">
                    <div className="h-6 w-24 bg-blue-100 rounded"></div>
                    <div className="h-6 w-20 bg-blue-100 rounded"></div>
                </div>
            </div>
        </div>
    );
}