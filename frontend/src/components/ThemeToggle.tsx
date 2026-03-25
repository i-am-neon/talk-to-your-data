import { Sun, Moon, Monitor } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Theme } from "@/hooks/useTheme";

const options: { value: Theme; label: string; icon: React.ReactNode }[] = [
  { value: "light", label: "Light", icon: <Sun className="size-4" /> },
  { value: "dark", label: "Dark", icon: <Moon className="size-4" /> },
  { value: "system", label: "System", icon: <Monitor className="size-4" /> },
];

export function ThemeToggle({
  theme,
  onChange,
}: {
  theme: Theme;
  onChange: (t: Theme) => void;
}) {
  return (
    <Select value={theme} onValueChange={(v) => { if (v) onChange(v as Theme); }}>
      <SelectTrigger size="sm" className="border-none bg-transparent shadow-none text-muted-foreground">
        <SelectValue>
          {options.find((o) => o.value === theme)?.icon}
          <span className="text-xs">{options.find((o) => o.value === theme)?.label}</span>
        </SelectValue>
      </SelectTrigger>
      <SelectContent align="end" alignItemWithTrigger={false}>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.icon}
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
