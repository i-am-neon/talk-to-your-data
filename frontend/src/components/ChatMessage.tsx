import { RefreshCw } from "lucide-react";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { DataChart } from "./DataChart";
import { Markdown } from "./Markdown";
import { ThinkingSection } from "./ThinkingSection";
import { isRetryable, getErrorMessage } from "../lib/errors";
import type { Message, ThinkingStep } from "../types";

/** Split steps into logical groups — a new group starts when a thinking/retry
 *  step follows a result or error step (i.e. the agent starts a new reasoning round). */
function groupSteps(steps: ThinkingStep[]): ThinkingStep[][] {
  const groups: ThinkingStep[][] = [];
  for (const step of steps) {
    const isNewRound =
      (step.type === "thinking" || step.type === "retry") &&
      groups.length > 0 &&
      groups[groups.length - 1].some((s) => s.type === "result" || s.type === "error");
    if (groups.length === 0 || isNewRound) {
      groups.push([step]);
    } else {
      groups[groups.length - 1].push(step);
    }
  }
  return groups;
}

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
  onArtifactClick?: (id: string) => void;
  onRetry?: () => void;
}

export function ChatMessage({ message, isStreaming = false, onArtifactClick, onRetry }: ChatMessageProps) {
  const isUser = message.role === "user";
  const hasSteps = message.steps && message.steps.length > 0;
  const hasContent = message.content.length > 0 || message.error;

  const stepGroups = hasSteps ? groupSteps(message.steps!) : [];
  const isWaiting = isStreaming && !hasSteps && !hasContent && !isUser;

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-message-in`}
    >
      <div className="max-w-[80%]">
        {isWaiting && (
          <div className="flex items-center gap-1.5 py-3 px-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="size-1.5 rounded-full bg-muted-foreground animate-pulse-dot"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        )}
        {!isUser && stepGroups.map((group, i) => (
          <ThinkingSection
            key={i}
            steps={group}
            isStreaming={isStreaming && !hasContent && i === stepGroups.length - 1}
          />
        ))}
        {(hasContent || !isStreaming) && (
          <div
            className={
              isUser
                ? "bg-primary/10 rounded-2xl rounded-br-sm px-4 py-2.5"
                : "py-1"
            }
          >
            {message.error ? (
              <div className="flex items-start gap-2">
                <p className="text-destructive text-sm">
                  {getErrorMessage(message.errorCode, message.error)}
                </p>
                {onRetry && isRetryable(message.errorCode) && (
                  <button
                    onClick={onRetry}
                    className="shrink-0 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mt-0.5"
                  >
                    <RefreshCw size={12} />
                    Retry
                  </button>
                )}
              </div>
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
        )}
      </div>
    </div>
  );
}
