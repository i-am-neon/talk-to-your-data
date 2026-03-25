import { useRef, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatInput } from "./components/ChatInput";
import { ChatMessage } from "./components/ChatMessage";
import { WorkspacePanel } from "./components/WorkspacePanel";
import { useChat } from "./hooks/useChat";
import { useArtifacts } from "./hooks/useArtifacts";

export default function App() {
  const artifactStore = useArtifacts();
  const { messages, isLoading, sendMessage } = useChat({
    getDescriptors: artifactStore.getDescriptors,
    processArtifact: artifactStore.processArtifact,
  });
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const hasArtifacts = artifactStore.artifacts.length > 0;

  return (
    <div className="flex h-screen">
      {/* Chat panel */}
      <div className={`flex flex-col p-4 transition-all duration-300 ${hasArtifacts ? "w-1/2 border-r" : "w-full max-w-3xl mx-auto"}`}>
        <h1 className="text-2xl font-bold mb-4">Talk to Your Data</h1>

        <ScrollArea className="flex-1 mb-4">
          <div className="space-y-4 pr-4">
            {messages.length === 0 && (
              <p className="text-muted-foreground text-center mt-8">
                Ask a question about the SaaS company dataset. Try: "What's the
                average ARR for fintech companies?"
              </p>
            )}
            {messages.map((msg, i) => (
              <ChatMessage
                key={i}
                message={msg}
                onArtifactClick={artifactStore.setSelectedId}
              />
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <Card className="max-w-[80%]">
                  <CardContent className="p-4 text-muted-foreground">
                    Analyzing...
                  </CardContent>
                </Card>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <ChatInput onSend={sendMessage} disabled={isLoading} />
      </div>

      {/* Workspace panel */}
      {hasArtifacts && (
        <div className="w-1/2 flex flex-col">
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
