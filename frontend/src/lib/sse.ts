import type { StreamEvent } from "../types";

/**
 * Parse a chunk of SSE text into individual events.
 * Handles partial chunks by returning unparsed remainder.
 */
export function parseSSEChunk(
  chunk: string,
  buffer: string
): { events: StreamEvent[]; remainder: string } {
  const text = buffer + chunk;
  const events: StreamEvent[] = [];
  const lines = text.split("\n");

  // Last element may be incomplete — keep as remainder
  const remainder = lines.pop() ?? "";

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("data: ")) {
      try {
        events.push(JSON.parse(trimmed.slice(6)) as StreamEvent);
      } catch {
        // Ignore malformed JSON
      }
    }
  }

  return { events, remainder };
}
