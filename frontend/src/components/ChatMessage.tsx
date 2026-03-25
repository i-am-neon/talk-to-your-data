import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { DataChart } from "./DataChart";
import { Markdown } from "./Markdown";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
  onArtifactClick?: (id: string) => void;
}

export function ChatMessage({ message, onArtifactClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-message-in`}
    >
      <div
        className={`max-w-[80%] ${
          isUser
            ? "bg-primary/10 rounded-2xl rounded-br-sm px-4 py-2.5"
            : "py-1"
        }`}
      >
        {message.error ? (
          <p className="text-destructive text-sm">{message.error}</p>
        ) : (
          <>
            <Markdown>{message.content}</Markdown>
            {message.artifactId ? (
              <button
                onClick={() => onArtifactClick?.(message.artifactId!)}
                className="mt-1 text-sm text-primary hover:underline cursor-pointer"
              >
                View in workspace &rarr;
              </button>
            ) : (
              <>
                {message.code && <CodeBlock code={message.code} />}
                {message.chart && <DataChart spec={message.chart} />}
                {!message.chart && message.images?.map((img, i) => (
                  <ChartImage key={i} src={img} />
                ))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
