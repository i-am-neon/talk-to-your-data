import { useState } from "react";

const SESSION_KEY = "session_id";

export function useSession(): string {
  const [sessionId] = useState<string>(() => {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  });
  return sessionId;
}
