export interface ArtifactVersion {
  content: string; // answer text associated with this version
  code?: string;
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
  images?: string[];
  error?: string;
  artifactId?: string; // links message to a workspace artifact
}

export interface QueryRequest {
  question: string;
  history: { role: "user" | "assistant"; content: string }[];
  artifacts: { id: string; title: string; type: string }[];
}

export interface QueryResponse {
  answer: string;
  code: string;
  images: string[];
  error: string | null;
  artifact: ArtifactMeta | null;
}
