import {
  Bar,
  BarChart,
  Line,
  LineChart,
  Area,
  AreaChart,
  Pie,
  PieChart,
  Radar,
  RadarChart,
  PolarAngleAxis,
  PolarGrid,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { ChartSpec } from "../types";

/** Turn a data key like "company_name" into "Company Name" */
function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildConfig(spec: ChartSpec): ChartConfig {
  const config: ChartConfig = {};
  if (spec.type === "pie") {
    spec.data.forEach((d, i) => {
      const name = String(d[spec.x_key] ?? `Slice ${i + 1}`);
      config[name] = {
        label: name,
        color: `var(--chart-${(i % 5) + 1})`,
      };
    });
  } else {
    spec.series.forEach((s, i) => {
      config[s.key] = {
        label: s.label,
        color: `var(--chart-${(i % 5) + 1})`,
      };
    });
  }
  return config;
}

function CartesianChart({
  spec,
  config,
  children,
}: {
  spec: ChartSpec;
  config: ChartConfig;
  children: (color: (key: string) => string) => React.ReactNode;
}) {
  const color = (key: string) => config[key]?.color ?? "var(--chart-1)";
  const ChartType =
    spec.type === "bar" ? BarChart : spec.type === "line" ? LineChart : AreaChart;

  const xLabel = humanize(spec.x_key);
  const yLabel = spec.series.length === 1 ? spec.series[0].label : undefined;

  return (
    <ChartContainer config={config} className="min-h-[300px] w-full">
      <ChartType data={spec.data} accessibilityLayer margin={{ bottom: yLabel ? 20 : 16, left: yLabel ? 20 : 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey={spec.x_key}
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          label={{ value: xLabel, position: "insideBottom", offset: -12, className: "fill-muted-foreground text-[11px]" }}
        />
        <YAxis
          tickLine={false}
          axisLine={false}
          tickMargin={8}
          label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", offset: -12, className: "fill-muted-foreground text-[11px]" } : undefined}
        />
        <ChartTooltip content={<ChartTooltipContent />} />
        {spec.series.length > 1 && (
          <ChartLegend content={<ChartLegendContent />} />
        )}
        {children(color)}
      </ChartType>
    </ChartContainer>
  );
}

function renderBar(spec: ChartSpec, config: ChartConfig) {
  return (
    <CartesianChart spec={spec} config={config}>
      {(color) =>
        spec.series.map((s) => (
          <Bar key={s.key} dataKey={s.key} fill={color(s.key)} radius={4} />
        ))
      }
    </CartesianChart>
  );
}

function renderLine(spec: ChartSpec, config: ChartConfig) {
  return (
    <CartesianChart spec={spec} config={config}>
      {(color) =>
        spec.series.map((s) => (
          <Line
            key={s.key}
            dataKey={s.key}
            stroke={color(s.key)}
            strokeWidth={2}
            dot={false}
            type="monotone"
          />
        ))
      }
    </CartesianChart>
  );
}

function renderArea(spec: ChartSpec, config: ChartConfig) {
  return (
    <CartesianChart spec={spec} config={config}>
      {(color) =>
        spec.series.map((s) => (
          <Area
            key={s.key}
            dataKey={s.key}
            fill={color(s.key)}
            stroke={color(s.key)}
            fillOpacity={0.3}
            type="monotone"
          />
        ))
      }
    </CartesianChart>
  );
}

function renderPie(spec: ChartSpec, config: ChartConfig) {
  const valueKey = spec.series[0]?.key ?? "value";
  return (
    <ChartContainer config={config} className="min-h-[300px] w-full">
      <PieChart accessibilityLayer>
        <ChartTooltip content={<ChartTooltipContent />} />
        <ChartLegend content={<ChartLegendContent />} />
        <Pie
          data={spec.data}
          dataKey={valueKey}
          nameKey={spec.x_key}
          cx="50%"
          cy="50%"
          innerRadius="40%"
          outerRadius="70%"
          paddingAngle={2}
        >
          {spec.data.map((_, i) => (
            <Cell key={i} fill={`var(--chart-${(i % 5) + 1})`} />
          ))}
        </Pie>
      </PieChart>
    </ChartContainer>
  );
}

function renderRadar(spec: ChartSpec, config: ChartConfig) {
  const color = (key: string) => config[key]?.color ?? "var(--chart-1)";
  return (
    <ChartContainer config={config} className="min-h-[300px] w-full">
      <RadarChart data={spec.data} accessibilityLayer>
        <PolarGrid />
        <PolarAngleAxis dataKey={spec.x_key} />
        <ChartTooltip content={<ChartTooltipContent />} />
        {spec.series.length > 1 && (
          <ChartLegend content={<ChartLegendContent />} />
        )}
        {spec.series.map((s) => (
          <Radar
            key={s.key}
            dataKey={s.key}
            fill={color(s.key)}
            fillOpacity={0.3}
            stroke={color(s.key)}
          />
        ))}
      </RadarChart>
    </ChartContainer>
  );
}

export function DataChart({ spec }: { spec: ChartSpec }) {
  const config = buildConfig(spec);

  switch (spec.type) {
    case "bar":
      return renderBar(spec, config);
    case "line":
      return renderLine(spec, config);
    case "area":
      return renderArea(spec, config);
    case "pie":
      return renderPie(spec, config);
    case "radar":
      return renderRadar(spec, config);
    default:
      return <p className="text-muted-foreground">Unsupported chart type: {spec.type}</p>;
  }
}
