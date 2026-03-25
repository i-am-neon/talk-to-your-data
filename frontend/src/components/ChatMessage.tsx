import { Card, CardContent } from "@/components/ui/card";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { Markdown } from "./Markdown";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
  onArtifactClick?: (id: string) => void;
}

export function ChatMessage({ message, onArtifactClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <Card
        className={`max-w-[80%] ${isUser ? "bg-primary text-primary-foreground" : ""}`}
      >
        <CardContent className="p-4">
          {message.error ? (
            <p className="text-destructive">{message.error}</p>
          ) : (
            <>
              <Markdown>{message.content}</Markdown>
              {message.artifactId ? (
                <button
                  onClick={() => onArtifactClick?.(message.artifactId!)}
                  className="mt-2 text-sm text-primary hover:underline cursor-pointer"
                >
                  View in workspace &rarr;
                </button>
              ) : (
                <>
                  {message.code && <CodeBlock code={message.code} />}
                  {message.images?.map((img, i) => (
                    <ChartImage key={i} src={img} />
                  ))}
                </>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
