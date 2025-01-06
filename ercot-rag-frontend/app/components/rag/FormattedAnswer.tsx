import type { Source } from '../../lib/types';

interface FormattedAnswerProps {
    content: string;
    sources: Source[];
}

export default function FormattedAnswer({ content, sources }: FormattedAnswerProps) {
    const processCitations = (html: string): string => {
        return html.replace(
            /<cite data-source-id="(\d+)">(.*?)<\/cite>/g,
            (_, id, text) => {
                const source = sources.find(s => s.metadata.document_id === Number(id));
                if (!source) return text;

                return `
                    <a 
                        href="#source-${id}" 
                        class="inline-block bg-blue-50 text-blue-700 px-2 py-1 rounded-lg 
                               hover:bg-blue-100 transition-colors"
                    >
                        ${text}
                    </a>
                `;
            }
        );
    };

    const cleanText = (text: string): string => {
        // Remove duplicate words dynamically
        return text.replace(/\b(\w+)\s+\1+\b/g, '$1');
    };

    return (
        <div className="prose max-w-none">
            <div 
                dangerouslySetInnerHTML={{ 
                    __html: processCitations(cleanText(content)) 
                }}
                className="
                    space-y-4
                    [&>h4]:text-lg 
                    [&>h4]:font-semibold 
                    [&>h4]:mt-6 
                    [&>h4]:mb-2
                    [&>p]:text-gray-700 
                    [&>p]:leading-relaxed
                    [&>ul]:list-disc 
                    [&>ul]:pl-5 
                    [&>ol]:list-decimal 
                    [&>ol]:pl-5
                    [&>li]:mb-2
                "
            />
        </div>
    );
}
