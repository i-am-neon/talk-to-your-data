import { useState, useCallback } from "react";
import type { Artifact, ArtifactMeta, ArtifactVersion, ChartSpec, TableSpec } from "../types";

export function useArtifacts() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const processArtifact = useCallback((
    meta: ArtifactMeta,
    content: { answer: string; code?: string; chart?: ChartSpec; table?: TableSpec; images?: string[] }
  ) => {
    const version: ArtifactVersion = {
      content: content.answer,
      code: content.code,
      chart: content.chart,
      table: content.table,
      images: content.images,
      timestamp: Date.now(),
    };

    setArtifacts(prev => {
      if (meta.action === "update") {
        return prev.map(a => a.id === meta.id ? {
          ...a,
          title: meta.title,
          versions: [...a.versions, version],
          currentVersion: a.versions.length,
        } : a);
      }
      // create
      return [...prev, {
        id: meta.id,
        title: meta.title,
        type: meta.type as Artifact["type"],
        versions: [version],
        currentVersion: 0,
      }];
    });

    setSelectedId(meta.id);
  }, []);

  const setVersion = useCallback((artifactId: string, versionIndex: number) => {
    setArtifacts(prev => prev.map(a =>
      a.id === artifactId ? { ...a, currentVersion: versionIndex } : a
    ));
  }, []);

  const loadFromConversation = useCallback((dbArtifacts: any[]) => {
    if (!dbArtifacts || dbArtifacts.length === 0) {
      setArtifacts([]);
      setSelectedId(null);
      return;
    }
    const grouped = new Map<string, { title: string; type: string; versions: ArtifactVersion[] }>();
    for (const a of dbArtifacts) {
      if (!grouped.has(a.artifact_id)) {
        grouped.set(a.artifact_id, { title: a.title, type: a.type, versions: [] });
      }
      const group = grouped.get(a.artifact_id)!;
      group.title = a.title;
      group.versions.push({
        content: "",
        code: a.code || undefined,
        chart: a.chart || undefined,
        table: a.table || undefined,
        images: a.images || undefined,
        timestamp: new Date(a.created_at).getTime(),
      });
    }
    const loaded: Artifact[] = [];
    for (const [id, data] of grouped) {
      loaded.push({
        id, title: data.title, type: data.type as Artifact["type"],
        versions: data.versions, currentVersion: data.versions.length - 1,
      });
    }
    setArtifacts(loaded);
    setSelectedId(loaded.length > 0 ? loaded[loaded.length - 1].id : null);
  }, []);

  const getDescriptors = useCallback(() =>
    artifacts.map(a => ({ id: a.id, title: a.title, type: a.type })),
    [artifacts]
  );

  return { artifacts, selectedId, setSelectedId, processArtifact, setVersion, getDescriptors, loadFromConversation };
}
