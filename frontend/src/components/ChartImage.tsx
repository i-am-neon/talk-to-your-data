interface ChartImageProps {
  src: string; // base64 PNG
}

export function ChartImage({ src }: ChartImageProps) {
  return (
    <img
      src={`data:image/png;base64,${src}`}
      alt="Chart"
      className="mt-2 rounded-lg max-w-full"
    />
  );
}
