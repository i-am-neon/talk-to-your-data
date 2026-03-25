import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Kbd } from "@/components/ui/kbd";
import type { ModelOption } from "@/types";

const MODEL_CYCLE: ModelOption[] = ["haiku", "sonnet", "opus"];

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  model: ModelOption;
  onModelChange: (model: ModelOption) => void;
}

export function ChatInput({ onSend, disabled, model, onModelChange }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.shiftKey && e.key === "Tab") {
        e.preventDefault();
        const idx = MODEL_CYCLE.indexOf(model);
        onModelChange(MODEL_CYCLE[(idx + 1) % MODEL_CYCLE.length]);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [model, onModelChange]);

  const resetHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value.trim());
      setValue("");
      resetHeight();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end border-t border-border pt-3">
      <div className="flex items-center gap-1 shrink-0 pb-1.5">
        <Kbd className="text-[10px]">⇧+Tab</Kbd>
        <Select value={model} onValueChange={(v) => v && onModelChange(v as ModelOption)}>
          <SelectTrigger size="sm" className="border-none bg-transparent shadow-none text-muted-foreground text-xs w-auto">
            <SelectValue className="capitalize" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="haiku">Haiku</SelectItem>
            <SelectItem value="sonnet">Sonnet</SelectItem>
            <SelectItem value="opus">Opus</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about the data..."
        disabled={disabled}
        rows={1}
        autoFocus
        className="flex-1 resize-none bg-transparent text-sm placeholder:text-muted-foreground
          focus:outline-none py-2 leading-relaxed"
      />
      <Button
        type="submit"
        disabled={disabled || !value.trim()}
        size="sm"
        className="shrink-0 mb-0.5"
      >
        {disabled ? (
          "..."
        ) : (
          <>
            Ask <Kbd data-icon="inline-end" className="translate-x-0.5">⏎</Kbd>
          </>
        )}
      </Button>
    </form>
  );
}
