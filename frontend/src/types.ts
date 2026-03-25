export interface ChartSeries {
  key: string;
  label: string;
}

export interface ChartSpec {
  type: "bar" | "line" | "area" | "pie" | "radar";
  data: Record<string, unknown>[];
  x_key: string;
  series: ChartSeries[];
}

export interface ColumnDef {
  key: string;
  label: string;
  dtype: string;
}

export interface TableSpec {
  columns: ColumnDef[];
  rows: Record<string, unknown>[];
}

export interface ArtifactVersion {
  content: string; // answer text associated with this version
  code?: string;
  chart?: ChartSpec;
  table?: TableSpec;
  images?: string[];
  timestamp: number;
}

export interface Artifact {
  id: string;
  title: string;
  type: "chart" | "table" | "code";
  versions: ArtifactVersion[];
  currentVersion: number;
}

export interface ArtifactMeta {
  id: string;
  title: string;
  type: string;
  action: "create" | "update";
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  code?: string;
  chart?: ChartSpec;
  images?: string[];
  error?: string;
  errorCode?: string;
  artifactId?: string; // links message to a workspace artifact
  steps?: ThinkingStep[];
}

export type ModelOption = "sonnet" | "opus" | "haiku";

export interface QueryRequest {
  question: string;
  conversation_id: string;
  model: ModelOption;
}

export interface QueryResponse {
  answer: string;
  code: string;
  chart: ChartSpec | null;
  table: TableSpec | null;
  images: string[];
  error: string | null;
  error_code: string | null;
  artifact: ArtifactMeta | null;
  conversation_id: string;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: {
    id: string;
    role: "user" | "assistant";
    content: string;
    code: string | null;
    images: string[] | null;
    chart: ChartSpec | null;
    table: TableSpec | null;
    artifact: ArtifactMeta | null;
    created_at: string;
  }[];
  artifacts: {
    id: string;
    artifact_id: string;
    title: string;
    type: "chart" | "table" | "code";
    version: number;
    code: string | null;
    images: string[] | null;
    chart: ChartSpec | null;
    table: TableSpec | null;
    created_at: string;
  }[];
}

// --- Streaming types ---

export interface ThinkingStep {
  type: "thinking" | "code" | "result" | "error" | "retry";
  content: string;
  fullCode?: string;
  chartsCount?: number;
}

export type StreamEvent =
  | { type: "thinking"; content: string }
  | { type: "tool_call_start"; tool: string; code: string }
  | { type: "tool_result"; stdout: string; images: string[]; charts_count: number }
  | { type: "tool_error"; error: string }
  | { type: "text_delta"; content: string }
  | {
      type: "done";
      answer: string;
      code: string;
      chart: ChartSpec | null;
      table: TableSpec | null;
      images: string[];
      artifact: ArtifactMeta | null;
      error: string | null;
      error_code?: string | null;
    };
