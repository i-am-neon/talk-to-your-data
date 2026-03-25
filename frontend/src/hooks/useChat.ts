import { useState, useRef, useCallback } from "react";
import type { Message, ArtifactMeta } from "../types";
import { queryAgent } from "../lib/api";

interface ArtifactHandlers {
  getDescriptors: () => { id: string; title: string; type: string }[];
  processArtifact: (meta: ArtifactMeta, content: { answer: string; code?: string; images?: string[] }) => void;
}

export function useChat(artifactHandlers: ArtifactHandlers) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;

  const sendMessage = useCallback(async (question: string) => {
    const userMessage: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const history = messagesRef.current.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await queryAgent({
        question,
        history,
        artifacts: artifactHandlers.getDescriptors(),
      });

      // If there's an artifact, route images/code to the artifact instead of inline
      const hasArtifact = response.artifact != null;

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        code: hasArtifact ? undefined : (response.code || undefined),
        images: hasArtifact ? undefined : (response.images.length > 0 ? response.images : undefined),
        error: response.error || undefined,
        artifactId: response.artifact?.id,
      };

      if (response.artifact) {
        artifactHandlers.processArtifact(response.artifact, {
          answer: response.answer,
          code: response.code || undefined,
          images: response.images.length > 0 ? response.images : undefined,
        });
      }

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: "assistant",
        content: "",
        error: err instanceof Error ? err.message : "Something went wrong",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [artifactHandlers]);

  return { messages, isLoading, sendMessage };
}
