import { useRef, useEffect, useState, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "./components/ChatInput";
import { ChatMessage } from "./components/ChatMessage";
import { EmptyState } from "./components/EmptyState";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { ThemeToggle } from "./components/ThemeToggle";
import { Sidebar } from "./components/Sidebar";
import { useSession } from "./hooks/useSession";
import { useConversations } from "./hooks/useConversations";
import { useChat } from "./hooks/useChat";
import { useArtifacts } from "./hooks/useArtifacts";
import { useTheme } from "./hooks/useTheme";
import { setSessionId } from "./lib/api";
import type { ModelOption } from "./types";

export default function App() {
  const sessionId = useSession();
  const [model, setModel] = useState<ModelOption>("sonnet");
  const { theme, setTheme } = useTheme();

  useEffect(() => { setSessionId(sessionId); }, [sessionId]);

  const { conversations, activeId, isLoading: convLoading, create, select, remove, refresh } = useConversations();
  const artifactStore = useArtifacts();

  const onConversationUpdate = useCallback(() => { refresh(); }, [refresh]);

  const { messages, isStreaming, isLoadingHistory, sendMessage } = useChat(
    {
      getDescriptors: artifactStore.getDescriptors,
      processArtifact: artifactStore.processArtifact,
      loadFromConversation: artifactStore.loadFromConversation,
    },
    model,
    activeId,
    onConversationUpdate,
  );

  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleNewChat = useCallback(async () => { await create(); }, [create]);

  const handleSend = useCallback(async (question: string) => {
    let id = activeId;
    if (!id) {
      id = await create();
    }
    sendMessage(question, id);
  }, [activeId, create, sendMessage]);

  const hasArtifacts = artifactStore.artifacts.length > 0;
  const hasMessages = messages.length > 0;
  const [workspaceCollapsed, setWorkspaceCollapsed] = useState(false);

  // Auto-expand workspace when a new artifact arrives
  const artifactCount = artifactStore.artifacts.length;
  const prevArtifactCount = useRef(artifactCount);
  useEffect(() => {
    if (artifactCount > prevArtifactCount.current) {
      setWorkspaceCollapsed(false);
    }
    prevArtifactCount.current = artifactCount;
  }, [artifactCount]);

  const workspaceOpen = hasArtifacts && !workspaceCollapsed;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        isLoading={convLoading}
        onSelect={select}
        onCreate={handleNewChat}
        onDelete={remove}
        footer={<ThemeToggle theme={theme} onChange={setTheme} />}
      />

      {/* Chat panel */}
      <div className={`flex flex-col min-h-0 overflow-hidden transition-all duration-300 ${workspaceOpen ? "w-1/2" : "flex-1 max-w-2xl mx-auto"}`}>

        {hasMessages ? (
          <ScrollArea className="flex-1 min-h-0 px-4">
            <div className="space-y-5 py-4 max-w-2xl mx-auto">
              {isLoadingHistory && (
                <p className="text-muted-foreground text-center mt-8">Loading conversation...</p>
              )}
              {messages.map((msg, i) => (
                <ChatMessage key={i} message={msg} isStreaming={isStreaming && i === messages.length - 1} onArtifactClick={(id) => { artifactStore.setSelectedId(id); setWorkspaceCollapsed(false); }} />
              ))}
              <div ref={bottomRef} />
            </div>
          </ScrollArea>
        ) : (
          <EmptyState onSuggestionClick={handleSend} />
        )}

        <div className="px-4 pb-4">
          <ChatInput onSend={handleSend} disabled={isStreaming || isLoadingHistory} model={model} onModelChange={setModel} />
        </div>
      </div>

      {/* Workspace panel */}
      {hasArtifacts && (
        <WorkspacePanel
          artifacts={artifactStore.artifacts}
          selectedId={artifactStore.selectedId}
          onSelect={artifactStore.setSelectedId}
          onVersionChange={artifactStore.setVersion}
          collapsed={workspaceCollapsed}
          onToggleCollapse={() => setWorkspaceCollapsed(!workspaceCollapsed)}
        />
      )}
    </div>
  );
}
