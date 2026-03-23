"use client";

import { useEffect, useRef } from "react";

interface OHLCVBar {
  time: number; // Unix timestamp (seconds)
  open: number;
  high: number;
  low: number;
  close: number;
}

interface PriceChartProps {
  symbol: string;
  data: OHLCVBar[];
  height?: number;
}

export default function PriceChart({ symbol, data, height = 300 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let chart: any;

    async function initChart() {
      try {
        const { createChart } = await import("lightweight-charts");

        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }

        chart = createChart(containerRef.current!, {
          width: containerRef.current!.clientWidth,
          height,
          layout: {
            background: { color: "#111318" },
            textColor: "#9ca3af",
          },
          grid: {
            vertLines: { color: "#1e2029" },
            horzLines: { color: "#1e2029" },
          },
          crosshair: {
            vertLine: { color: "#6b7280", width: 1, style: 3 },
            horzLine: { color: "#6b7280", width: 1, style: 3 },
          },
          rightPriceScale: {
            borderColor: "#1e2029",
            textColor: "#9ca3af",
          },
          timeScale: {
            borderColor: "#1e2029",
            timeVisible: true,
            secondsVisible: false,
          },
          handleScale: true,
          handleScroll: true,
        });

        chartRef.current = chart;

        const candleSeries = chart.addCandlestickSeries({
          upColor: "#00d4aa",
          downColor: "#ff3b5c",
          borderUpColor: "#00d4aa",
          borderDownColor: "#ff3b5c",
          wickUpColor: "#00d4aa",
          wickDownColor: "#ff3b5c",
        });

        seriesRef.current = candleSeries;

        if (data && data.length > 0) {
          const sorted = [...data].sort((a, b) => a.time - b.time);
          candleSeries.setData(sorted);
          chart.timeScale().fitContent();
        }

        // Resize observer
        const ro = new ResizeObserver(() => {
          if (containerRef.current && chart) {
            chart.applyOptions({ width: containerRef.current.clientWidth });
          }
        });
        if (containerRef.current) ro.observe(containerRef.current);

        return () => {
          ro.disconnect();
        };
      } catch (err) {
        console.error("Chart init error:", err);
      }
    }

    initChart();

    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        seriesRef.current = null;
      }
    };
  }, [symbol, height]);

  // Update data without recreating chart
  useEffect(() => {
    if (seriesRef.current && data && data.length > 0) {
      const sorted = [...data].sort((a, b) => a.time - b.time);
      seriesRef.current.setData(sorted);
      if (chartRef.current) {
        chartRef.current.timeScale().fitContent();
      }
    }
  }, [data]);

  return (
    <div className="relative">
      <div className="absolute top-2 left-3 z-10 text-xs text-text-secondary font-medium">
        {symbol} — Candlestick
      </div>
      <div
        ref={containerRef}
        style={{ width: "100%", height }}
        className="rounded-lg overflow-hidden"
      />
      {(!data || data.length === 0) && (
        <div className="absolute inset-0 flex items-center justify-center text-muted text-sm">
          No chart data available
        </div>
      )}
    </div>
  );
}
