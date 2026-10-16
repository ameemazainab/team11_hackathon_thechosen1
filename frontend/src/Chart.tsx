import { useEffect, useRef } from "react";
import { BarController, BarElement, CategoryScale, Chart as ChartJS, Filler, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip, type ChartConfiguration } from "chart.js";

ChartJS.register(BarController, BarElement, LineController, LineElement, PointElement, CategoryScale, LinearScale, Legend, Tooltip, Filler);
export const PALETTE = { committed: "#1f3a5f", weighted: "#e08a00", total: "#2e7d32", was: "#6b7280", now: "#1f3a5f", gap: "#b42318" };

/** Thin wrapper so pages only describe the chart. `summary` is the text alternative for screen readers. */
export function Chart({ config, summary, height = 280 }: { config: ChartConfiguration; summary: string; height?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = new ChartJS(ref.current, { ...config, options: { responsive: true, maintainAspectRatio: false, animation: false, ...(config.options ?? {}) } });
    return () => chart.destroy();
  }, [config]);
  return (
    <div style={{ height }}>
      <canvas ref={ref} role="img" aria-label={summary} />
    </div>
  );
}

export const moneyAxis = { ticks: { callback: (v: string | number) => "$" + (Number(v) / 1e6).toFixed(1) + "M" } };
