// app/components/ui/Button.tsx
'use client';

import { ButtonHTMLAttributes, forwardRef } from 'react';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    isLoading?: boolean;
    variant?: 'default' | 'secondary' | 'outline';
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(({
    className = '',
    children,
    isLoading = false,
    variant = 'default',
    disabled,
    ...props
}, ref) => {
    const baseStyles = 'inline-flex items-center justify-center px-4 py-2 rounded-md font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 transition-colors';
    const variantStyles = {
        default: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
        secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-500',
        outline: 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 focus:ring-blue-500'
    };

    return (
        <button
            ref={ref}
            className={`${baseStyles} ${variantStyles[variant]} ${className}`}
            disabled={isLoading || disabled}
            {...props}
        >
            {isLoading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {children}
        </button>
    );
});

Button.displayName = 'Button';
export default Button;

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