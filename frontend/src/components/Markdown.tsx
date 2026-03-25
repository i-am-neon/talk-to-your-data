import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  children: string;
}

export function Markdown({ children }: MarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }) => (
          <div className="my-2 overflow-x-auto">
            <table className="min-w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-muted">{children}</thead>
        ),
        th: ({ children }) => (
          <th className="border px-3 py-1.5 text-left font-medium">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border px-3 py-1.5">{children}</td>
        ),
        pre: ({ children }) => (
          <pre className="my-2 p-3 bg-muted rounded-md overflow-x-auto text-sm">{children}</pre>
        ),
        code: ({ children, className }) => {
          const isBlock = className?.startsWith("language-");
          if (isBlock) return <code className={className}>{children}</code>;
          return <code className="bg-muted px-1 py-0.5 rounded text-sm">{children}</code>;
        },
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        ul: ({ children }) => <ul className="list-disc pl-5 mb-2">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-2">{children}</ol>,
        li: ({ children }) => <li className="mb-0.5">{children}</li>,
        h1: ({ children }) => <h1 className="text-xl font-bold mt-3 mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-semibold mt-3 mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold mt-2 mb-1">{children}</h3>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
