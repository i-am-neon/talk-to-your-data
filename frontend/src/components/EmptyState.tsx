const SUGGESTIONS = [
  "Average ARR by industry vertical",
  "Top 10 fastest-growing companies",
  "Companies with under 5% churn rate",
  "Employee count vs. ARR correlation",
];

interface EmptyStateProps {
  onSuggestionClick: (query: string) => void;
}

export function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 px-4">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-heading font-bold tracking-tight">
          Talk to Your Data
        </h1>
        <p className="text-muted-foreground text-sm max-w-sm">
          Ask questions about SaaS company metrics in plain English.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2 max-w-lg">
        {SUGGESTIONS.map((query) => (
          <button
            key={query}
            onClick={() => onSuggestionClick(query)}
            className="px-3 py-1.5 text-sm border border-border rounded-full
              text-muted-foreground hover:text-foreground hover:border-primary/40
              hover:bg-primary/5 transition-colors cursor-pointer"
          >
            {query}
          </button>
        ))}
      </div>
    </div>
  );
}
