import { useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface CodeBlockProps {
  code: string;
}

export function CodeBlock({ code }: CodeBlockProps) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger className="text-sm text-muted-foreground hover:underline cursor-pointer">
        {open ? "Hide code" : "Show code"}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-2 p-3 bg-muted rounded-md overflow-x-auto text-sm">
          <code>{code}</code>
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
