import type { QueryRequest, QueryResponse, StreamEvent, ConversationSummary, ConversationDetail } from "../types";
import { parseSSEChunk } from "./sse";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

let _sessionId = "";

export function setSessionId(id: string) {
  _sessionId = id;
}

function headers(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "X-Session-ID": _sessionId,
  };
}

export async function queryAgent(req: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(req),
  });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export function queryAgentStream(
  req: QueryRequest,
  onEvent: (event: StreamEvent) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${API_URL}/api/query/stream`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(req),
        signal: controller.signal,
      });

      if (!response.ok) {
        onEvent({
          type: "done",
          answer: "",
          code: "",
          chart: null,
          table: null,
          images: [],
          artifact: null,
          error: `API error: ${response.status}`,
        });
        return;
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const { events, remainder } = parseSSEChunk(chunk, buffer);
        buffer = remainder;

        for (const event of events) {
          onEvent(event);
        }
      }

      if (buffer.trim()) {
        const { events } = parseSSEChunk("\n", buffer);
        for (const event of events) {
          onEvent(event);
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onEvent({
          type: "done",
          answer: "",
          code: "",
          chart: null,
          table: null,
          images: [],
          artifact: null,
          error: err instanceof Error ? err.message : "Something went wrong",
        });
      }
    }
  })();

  return controller;
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const response = await fetch(`${API_URL}/api/conversations`, { headers: headers() });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function createConversation(): Promise<ConversationSummary> {
  const response = await fetch(`${API_URL}/api/conversations`, { method: "POST", headers: headers() });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const response = await fetch(`${API_URL}/api/conversations/${id}`, { headers: headers() });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/conversations/${id}`, { method: "DELETE", headers: headers() });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
}
