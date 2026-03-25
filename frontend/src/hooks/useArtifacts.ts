import { useState, useCallback } from "react";
import type { Artifact, ArtifactMeta, ArtifactVersion } from "../types";

export function useArtifacts() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const processArtifact = useCallback((
    meta: ArtifactMeta,
    content: { answer: string; code?: string; images?: string[] }
  ) => {
    const version: ArtifactVersion = {
      content: content.answer,
      code: content.code,
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

  const getDescriptors = useCallback(() =>
    artifacts.map(a => ({ id: a.id, title: a.title, type: a.type })),
    [artifacts]
  );

  return { artifacts, selectedId, setSelectedId, processArtifact, setVersion, getDescriptors };
}
