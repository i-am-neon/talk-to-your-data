import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CodeBlock } from "./CodeBlock";
import { ChartImage } from "./ChartImage";
import { DataChart } from "./DataChart";
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

  return (
    <div className="flex flex-col h-full">
      {/* Artifact tabs at top */}
      <div className="border-b border-border px-3 py-2 flex gap-1 overflow-x-auto">
        {artifacts.map((artifact) => (
          <button
            key={artifact.id}
            onClick={() => onSelect(artifact.id)}
            className={`shrink-0 px-3 py-1 text-sm rounded-full transition-colors cursor-pointer ${
              artifact.id === selectedId
                ? "bg-primary/15 text-primary font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {artifact.title}
          </button>
        ))}
      </div>

      {selected ? (
        <>
          {/* Version nav — only when multiple versions */}
          {selected.versions.length > 1 && (
            <div className="flex items-center justify-end gap-1 px-4 py-2 text-sm text-muted-foreground">
              <span>
                v{selected.currentVersion + 1}/{selected.versions.length}
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={selected.currentVersion === 0}
                onClick={() =>
                  onVersionChange(selected.id, selected.currentVersion - 1)
                }
              >
                &lt;
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                disabled={
                  selected.currentVersion === selected.versions.length - 1
                }
                onClick={() =>
                  onVersionChange(selected.id, selected.currentVersion + 1)
                }
              >
                &gt;
              </Button>
            </div>
          )}

          {/* Content */}
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-4">
              {/* Chart (interactive) */}
              {selected.versions[selected.currentVersion].chart && (
                <DataChart spec={selected.versions[selected.currentVersion].chart!} />
              )}
              {/* Chart images (matplotlib fallback) */}
              {!selected.versions[selected.currentVersion].chart &&
                selected.versions[selected.currentVersion].images?.map(
                  (img, i) => <ChartImage key={i} src={img} />
                )}
              {/* Text content */}
              {!selected.versions[selected.currentVersion].chart &&
                !selected.versions[selected.currentVersion].images?.length &&
                selected.versions[selected.currentVersion].content && (
                  <Markdown>
                    {selected.versions[selected.currentVersion].content}
                  </Markdown>
                )}
              {selected.versions[selected.currentVersion].code && (
                <CodeBlock
                  code={selected.versions[selected.currentVersion].code!}
                />
              )}
            </div>
          </ScrollArea>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Select an artifact to view
        </div>
      )}
    </div>
  );
}
