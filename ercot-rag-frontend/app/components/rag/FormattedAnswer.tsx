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
                // Match source to highlight properly
                const source = sources.find(s => s.metadata.document_id === Number(id));
                if (!source) return text;

                return `<a 
                    href="#source-${id}" 
                    class="inline-flex items-center px-1 py-0.5 rounded bg-blue-50 
                           text-blue-700 hover:bg-blue-100 transition-colors"
                    onclick="document.getElementById('source-${id}').scrollIntoView({behavior:'smooth'})"
                >${text}</a>`;
            }
        );
    };

    return (
        <div 
            dangerouslySetInnerHTML={{ 
                __html: processCitations(content) 
            }}
            className="
                prose max-w-none
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
    );
}
