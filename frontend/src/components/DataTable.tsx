import { useState, useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import type { TableSpec } from "../types";

interface DataTableProps {
  spec: TableSpec;
}

type SortDirection = "asc" | "desc" | null;

function isNumericDtype(dtype: string): boolean {
  return /int|float|decimal|numeric/i.test(dtype);
}

export function DataTable({ spec }: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);

  const handleSort = (key: string) => {
    if (sortKey !== key) {
      setSortKey(key);
      setSortDir("asc");
    } else if (sortDir === "asc") {
      setSortDir("desc");
    } else {
      setSortKey(null);
      setSortDir(null);
    }
  };

  const sortedRows = useMemo(() => {
    if (!sortKey || !sortDir) return spec.rows;
    const col = spec.columns.find((c) => c.key === sortKey);
    const numeric = col ? isNumericDtype(col.dtype) : false;
    return [...spec.rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      let cmp: number;
      if (numeric) {
        cmp = Number(av) - Number(bv);
      } else {
        cmp = String(av).localeCompare(String(bv));
      }
      return sortDir === "desc" ? -cmp : cmp;
    });
  }, [spec.rows, spec.columns, sortKey, sortDir]);

  const formatCell = (value: unknown, dtype: string): string => {
    if (value == null) return "";
    if (isNumericDtype(dtype) && typeof value === "number") {
      return Number.isInteger(value)
        ? value.toLocaleString()
        : value.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
          });
    }
    return String(value);
  };

  return (
    <div className="overflow-auto max-h-[calc(100vh-12rem)]">
      <Table>
        <TableHeader className="sticky top-0 bg-background z-10">
          <TableRow>
            {spec.columns.map((col) => {
              const numeric = isNumericDtype(col.dtype);
              const isActive = sortKey === col.key;
              return (
                <TableHead
                  key={col.key}
                  className={`cursor-pointer select-none hover:bg-muted/50 ${
                    numeric ? "text-right" : ""
                  }`}
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    {isActive && sortDir === "asc" ? (
                      <ChevronUp className="h-3.5 w-3.5" />
                    ) : isActive && sortDir === "desc" ? (
                      <ChevronDown className="h-3.5 w-3.5" />
                    ) : (
                      <ChevronsUpDown className="h-3.5 w-3.5 opacity-30" />
                    )}
                  </span>
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedRows.map((row, i) => (
            <TableRow key={i} className={i % 2 === 1 ? "bg-muted/30" : ""}>
              {spec.columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={isNumericDtype(col.dtype) ? "text-right tabular-nums" : ""}
                >
                  {formatCell(row[col.key], col.dtype)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
