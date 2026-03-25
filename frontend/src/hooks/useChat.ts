import { useState, useRef, useCallback, useEffect } from "react";
import type { Message, ArtifactMeta, ModelOption, StreamEvent } from "../types";
import { queryAgentStream, getConversation } from "../lib/api";

interface ArtifactHandlers {
  getDescriptors: () => { id: string; title: string; type: string }[];
  processArtifact: (meta: ArtifactMeta, content: { answer: string; code?: string; images?: string[] }) => void;
  loadFromConversation: (artifacts: any[]) => void;
}

export function useChat(
  artifactHandlers: ArtifactHandlers,
  model: ModelOption,
  conversationId: string | null,
  onConversationUpdate: () => void,
) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const lastWasErrorRef = useRef(false);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    setIsLoadingHistory(true);

    getConversation(conversationId)
      .then((conv) => {
        if (cancelled) return;
        const loaded: Message[] = conv.messages.map((m) => ({
          role: m.role,
          content: m.content,
          code: m.code || undefined,
          images: m.images || undefined,
          artifactId: m.artifact?.id,
        }));
        setMessages(loaded);
        artifactHandlers.loadFromConversation(conv.artifacts);
      })
      .catch((err) => {
        if (!cancelled) console.error("Failed to load conversation:", err);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingHistory(false);
      });

    return () => { cancelled = true; };
  }, [conversationId]); // eslint-disable-line react-hooks/exhaustive-deps

  const updateLastMessage = useCallback((updater: (msg: Message) => Message) => {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last && last.role === "assistant") {
        updated[updated.length - 1] = updater(last);
      }
      return updated;
    });
  }, []);

  const handleEvent = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case "thinking": {
          updateLastMessage((msg) => {
            const steps = [...(msg.steps ?? [])];
            const last = steps[steps.length - 1];

            if (lastWasErrorRef.current) {
              steps.push({ type: "retry", content: event.content });
              lastWasErrorRef.current = false;
            } else if (last && (last.type === "thinking" || last.type === "retry")) {
              steps[steps.length - 1] = { ...last, content: last.content + event.content };
            } else {
              steps.push({ type: "thinking", content: event.content });
            }

            return { ...msg, steps };
          });
          break;
        }

        case "tool_call_start": {
          const firstLine = event.code.split("\n")[0];
          updateLastMessage((msg) => ({
            ...msg,
            steps: [
              ...(msg.steps ?? []),
              { type: "code", content: firstLine, fullCode: event.code },
            ],
          }));
          break;
        }

        case "tool_result": {
          const desc = event.stdout
            ? event.stdout.slice(0, 80) + (event.stdout.length > 80 ? "..." : "")
            : "Code executed";
          updateLastMessage((msg) => ({
            ...msg,
            steps: [
              ...(msg.steps ?? []),
              { type: "result", content: desc, chartsCount: event.charts_count },
            ],
          }));
          break;
        }

        case "tool_error": {
          lastWasErrorRef.current = true;
          updateLastMessage((msg) => ({
            ...msg,
            steps: [...(msg.steps ?? []), { type: "error", content: event.error }],
          }));
          break;
        }

        case "text_delta": {
          updateLastMessage((msg) => ({
            ...msg,
            content: msg.content + event.content,
          }));
          break;
        }

        case "done": {
          lastWasErrorRef.current = false;

          updateLastMessage((msg) => {
            const updated: Message = {
              ...msg,
              content: event.answer ?? msg.content,
              code: event.artifact ? undefined : event.code || undefined,
              images: event.artifact
                ? undefined
                : event.images.length > 0
                  ? event.images
                  : undefined,
              error: event.error || undefined,
              artifactId: event.artifact?.id,
            };
            return updated;
          });

          if (event.artifact) {
            artifactHandlers.processArtifact(event.artifact, {
              answer: event.answer ?? "",
              code: event.code || undefined,
              images: event.images.length > 0 ? event.images : undefined,
            });
          }

          onConversationUpdate();
          setIsStreaming(false);
          break;
        }
      }
    },
    [updateLastMessage, artifactHandlers, onConversationUpdate]
  );

  const sendMessage = useCallback(
    (question: string, overrideConversationId?: string) => {
      const convId = overrideConversationId || conversationId;
      if (!convId) return;

      const userMessage: Message = { role: "user", content: question };
      const assistantMessage: Message = { role: "assistant", content: "", steps: [] };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsStreaming(true);
      lastWasErrorRef.current = false;

      queryAgentStream(
        {
          question,
          conversation_id: convId,
          model,
        },
        handleEvent
      );
    },
    [conversationId, model, handleEvent]
  );

  return { messages, isStreaming, isLoadingHistory, sendMessage };
}
