import { useState } from "react";
import {
  Brain,
  Play,
  BarChart3,
  CircleX,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import type { ThinkingStep } from "../types";

interface ThinkingSectionProps {
  steps: ThinkingStep[];
  isStreaming: boolean;
}

function buildSummary(steps: ThinkingStep[]): string {
  const parts: string[] = [];
  let codeCount = 0;

  for (const step of steps) {
    switch (step.type) {
      case "thinking":
        if (parts.length === 0 || parts[parts.length - 1] !== "thought") {
          parts.push("thought");
        }
        break;
      case "code":
        codeCount++;
        break;
      case "result":
        break;
      case "error":
        break;
      case "retry":
        parts.push("ran code");
        parts.push("retried");
        codeCount = 0;
        break;
    }
  }

  if (codeCount === 1) {
    parts.push("ran code");
  } else if (codeCount > 1) {
    parts.push(`ran code ${codeCount}x`);
  }

  return parts.length > 0
    ? parts.map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(", ")
    : "Thought";
}

const stepConfig = {
  thinking: { icon: Brain, activeLabel: "Thinking", doneLabel: "Thought", color: "text-purple-400", bg: "bg-purple-500/10" },
  code: { icon: Play, activeLabel: "Running code", doneLabel: "Ran code", color: "text-amber-400", bg: "bg-amber-500/10" },
  result: { icon: BarChart3, activeLabel: "Result", doneLabel: "Result", color: "text-cyan-400", bg: "bg-cyan-500/10" },
  error: { icon: CircleX, activeLabel: "Error", doneLabel: "Error", color: "text-red-400", bg: "bg-red-500/10" },
  retry: { icon: RefreshCw, activeLabel: "Retrying", doneLabel: "Retried", color: "text-purple-400", bg: "bg-purple-500/10" },
} as const;

function StepBadge({ type, isActive }: { type: ThinkingStep["type"]; isActive?: boolean }) {
  const config = stepConfig[type];
  const Icon = config.icon;
  const label = isActive ? config.activeLabel : config.doneLabel;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-semibold whitespace-nowrap ${config.bg} ${config.color}`}
    >
      <Icon size={12} className={isActive ? "animate-pulse" : ""} />
      {label}
    </span>
  );
}

function CodeStep({ step }: { step: ThinkingStep }) {
  const [expanded, setExpanded] = useState(false);
  const firstLine = step.content.split("\n")[0];

  return (
    <div className="flex flex-col gap-1.5 flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <code className="text-xs bg-white/5 px-2 py-0.5 rounded truncate max-w-[400px]">
          {firstLine}
        </code>
        {step.fullCode && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-purple-400 text-xs font-medium inline-flex items-center gap-1 whitespace-nowrap hover:text-purple-300"
          >
            <ChevronDown
              size={11}
              className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "hide" : "show full"}
          </button>
        )}
      </div>
      <div
        className="grid transition-[grid-template-rows] duration-250 ease-in-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <pre className="overflow-hidden text-xs bg-black/30 rounded-md text-gray-300 whitespace-pre-wrap leading-relaxed m-0"
          style={{ padding: expanded ? "10px" : "0 10px" }}
        >
          {step.fullCode}
        </pre>
      </div>
    </div>
  );
}

function ErrorStep({ step }: { step: ThinkingStep }) {
  const [expanded, setExpanded] = useState(false);
  const firstLine = step.content.split("\n")[0];
  const isMultiline = step.content.includes("\n");

  return (
    <div className="flex flex-col gap-1.5 flex-1 min-w-0">
      <div className="flex items-center gap-2">
        <span className="text-red-400 text-xs truncate max-w-[400px]">{firstLine}</span>
        {isMultiline && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-red-400/70 text-xs font-medium inline-flex items-center gap-1 whitespace-nowrap hover:text-red-300"
          >
            <ChevronDown
              size={11}
              className={`transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
            />
            {expanded ? "hide" : "show full"}
          </button>
        )}
      </div>
      {isMultiline && (
        <div
          className="grid transition-[grid-template-rows] duration-250 ease-in-out"
          style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
        >
          <pre className="overflow-hidden text-xs bg-red-500/5 rounded-md text-red-400 whitespace-pre-wrap leading-relaxed m-0"
            style={{ padding: expanded ? "10px" : "0 10px" }}
          >
            {step.content}
          </pre>
        </div>
      )}
    </div>
  );
}

function StepItem({ step, isActive }: { step: ThinkingStep; isActive?: boolean }) {
  if (step.type === "thinking" || step.type === "retry") {
    return (
      <p className="text-muted-foreground text-xs leading-relaxed m-0 whitespace-pre-wrap">
        {step.content}
      </p>
    );
  }

  return (
    <div className="flex items-start gap-2 text-sm">
      <StepBadge type={step.type} isActive={isActive} />
      {step.type === "code" ? (
        <CodeStep step={step} />
      ) : step.type === "result" ? (
        <span className="text-gray-300 text-xs">
          {step.content}
          {step.chartsCount ? ` + ${step.chartsCount} chart(s)` : ""}
        </span>
      ) : step.type === "error" ? (
        <ErrorStep step={step} />
      ) : null}
    </div>
  );
}

function LiveLabel({ steps }: { steps: ThinkingStep[] }) {
  const last = steps[steps.length - 1];
  if (!last) return null;
  const config = stepConfig[last.type];
  return <span className="animate-pulse">{config.activeLabel}...</span>;
}

export function ThinkingSection({ steps, isStreaming }: ThinkingSectionProps) {
  const [expanded, setExpanded] = useState(false);

  if (steps.length === 0) return null;

  const summary = buildSummary(steps);

  return (
    <div className="mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="inline-flex items-center gap-1.5 bg-purple-500/8 border border-purple-500/15 rounded-lg px-3 py-1.5 text-sm text-purple-400 hover:bg-purple-500/12 transition-colors cursor-pointer"
      >
        <Brain size={14} className={isStreaming ? "animate-pulse" : ""} />
        <span>{isStreaming ? <LiveLabel steps={steps} /> : summary}</span>
        <ChevronDown
          size={12}
          className={`transition-transform duration-250 ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-in-out"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="mt-2 ml-1 pl-4 border-l-2 border-purple-500/20 flex flex-col gap-2.5">
            {steps.map((step, i) => (
              <StepItem key={i} step={step} isActive={isStreaming && i === steps.length - 1} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
