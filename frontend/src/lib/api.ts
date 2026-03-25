import type { QueryRequest, QueryResponse } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function queryAgent(req: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  return response.json();
}
