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

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        isLoading={convLoading}
        onSelect={select}
        onCreate={handleNewChat}
        onDelete={remove}
      />

      {/* Chat panel */}
      <div className={`flex flex-col min-h-0 transition-all duration-300 ${hasArtifacts ? "w-1/2" : "flex-1 max-w-2xl mx-auto"}`}>
        <div className="flex items-center justify-end px-4 py-2">
          <ThemeToggle theme={theme} onChange={setTheme} />
        </div>

        {hasMessages ? (
          <ScrollArea className="flex-1 px-4">
            <div className="space-y-5 py-4 max-w-2xl mx-auto">
              {isLoadingHistory && (
                <p className="text-muted-foreground text-center mt-8">Loading conversation...</p>
              )}
              {messages.map((msg, i) => (
                <ChatMessage key={i} message={msg} isStreaming={isStreaming && i === messages.length - 1} onArtifactClick={artifactStore.setSelectedId} />
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
        <div className="w-1/2 border-l border-border animate-slide-in-right">
          <WorkspacePanel
            artifacts={artifactStore.artifacts}
            selectedId={artifactStore.selectedId}
            onSelect={artifactStore.setSelectedId}
            onVersionChange={artifactStore.setVersion}
          />
        </div>
      )}
    </div>
  );
}
