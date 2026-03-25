import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { Markdown } from "./Markdown";
import type { Artifact } from "../types";

interface WorkspacePanelProps {
  artifacts: Artifact[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onVersionChange: (artifactId: string, versionIndex: number) => void;
}

export function WorkspacePanel({
  artifacts,
  selectedId,
  onSelect,
  onVersionChange,
}: WorkspacePanelProps) {
  const selected = artifacts.find((a) => a.id === selectedId) ?? null;

  if (!selected) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground">
        Select an artifact to view
      </div>
    );
  }

  const version = selected.versions[selected.currentVersion];
  const totalVersions = selected.versions.length;
  const currentIdx = selected.currentVersion;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-lg font-semibold truncate">{selected.title}</h2>
        <div className="flex items-center gap-1 shrink-0 ml-2">
          <span className="text-sm text-muted-foreground mr-1">
            v{currentIdx + 1}/{totalVersions}
          </span>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={currentIdx === 0}
            onClick={() => onVersionChange(selected.id, currentIdx - 1)}
          >
            &lt;
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            disabled={currentIdx === totalVersions - 1}
            onClick={() => onVersionChange(selected.id, currentIdx + 1)}
          >
            &gt;
          </Button>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-4">
          {/* Chart images */}
          {version.images?.map((img, i) => (
            <ChartImage key={i} src={img} />
          ))}

          {/* Non-chart artifacts: show stdout as formatted output */}
          {!version.images?.length && version.content && (
            <Markdown>{version.content}</Markdown>
          )}

          {/* Collapsible source code */}
          {version.code && <CodeBlock code={version.code} />}
        </div>
      </ScrollArea>

      {/* Artifact tabs */}
      <div className="border-t px-2 py-2 flex gap-1 overflow-x-auto">
        {artifacts.map((artifact) => (
          <Button
            key={artifact.id}
            variant={artifact.id === selectedId ? "secondary" : "ghost"}
            size="sm"
            className="shrink-0 max-w-[160px] truncate"
            onClick={() => onSelect(artifact.id)}
          >
            {artifact.title}
          </Button>
        ))}
      </div>
    </div>
  );
}
