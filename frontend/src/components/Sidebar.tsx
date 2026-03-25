import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PanelLeftClose, PanelLeft, Plus, Trash2 } from "lucide-react";
import type { ConversationSummary } from "@/types";

interface SidebarProps {
  conversations: ConversationSummary[];
  activeId: string | null;
  isLoading: boolean;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}

export function Sidebar({ conversations, activeId, isLoading, onSelect, onCreate, onDelete }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  if (collapsed) {
    return (
      <div className="w-10 border-r flex flex-col items-center pt-2">
        <Button variant="ghost" size="icon-sm" onClick={() => setCollapsed(false)}>
          <PanelLeft className="h-4 w-4" />
        </Button>
      </div>
    );
  }

  return (
    <div className="w-64 border-r flex flex-col bg-muted/30">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="text-sm font-semibold">History</span>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon-sm" onClick={onCreate}>
            <Plus className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon-sm" onClick={() => setCollapsed(true)}>
            <PanelLeftClose className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-2 space-y-1">
          {isLoading && [1, 2, 3].map((i) => (
            <div key={i} className="h-9 rounded-md bg-muted animate-pulse" />
          ))}
          {!isLoading && conversations.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">No conversations yet</p>
          )}
          {conversations.map((conv) => (
            <div
              key={conv.id}
              className={`group flex items-center gap-1 rounded-md px-2 py-1.5 text-sm cursor-pointer hover:bg-muted ${conv.id === activeId ? "bg-muted" : ""}`}
              onClick={() => onSelect(conv.id)}
            >
              <span className="truncate flex-1">{conv.title || "New conversation"}</span>
              {confirmDelete === conv.id ? (
                <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                  <Button variant="destructive" size="icon-sm" onClick={() => { onDelete(conv.id); setConfirmDelete(null); }}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                  <Button variant="ghost" size="icon-sm" onClick={() => setConfirmDelete(null)}>
                    ✕
                  </Button>
                </div>
              ) : (
                <Button variant="ghost" size="icon-sm" className="opacity-0 group-hover:opacity-100 shrink-0"
                  onClick={(e) => { e.stopPropagation(); setConfirmDelete(conv.id); }}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
