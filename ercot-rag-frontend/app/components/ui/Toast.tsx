// app/components/ui/Toast.tsx
'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface ToastProps {
    message: string;
    type?: 'success' | 'error' | 'info';
    duration?: number;
    onClose?: () => void;
}

export default function Toast({ 
    message, 
    type = 'info', 
    duration = 5000, 
    onClose 
}: ToastProps) {
    const [isVisible, setIsVisible] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIsVisible(false);
            onClose?.();
        }, duration);

        return () => clearTimeout(timer);
    }, [duration, onClose]);

    if (!isVisible) return null;

    const styles = {
        success: 'bg-green-50 text-green-800 border-green-200',
        error: 'bg-red-50 text-red-800 border-red-200',
        info: 'bg-blue-50 text-blue-800 border-blue-200'
    };

    return (
        <div className={`fixed bottom-4 right-4 p-4 rounded-lg border ${styles[type]} shadow-lg max-w-md animate-slide-up`}>
            <div className="flex items-center justify-between">
                <p>{message}</p>
                <button
                    onClick={() => {
                        setIsVisible(false);
                        onClose?.();
                    }}
                    className="ml-4 text-current opacity-50 hover:opacity-100 transition-opacity"
                >
                    <X size={16} />
                </button>
            </div>
        </div>
    );
}