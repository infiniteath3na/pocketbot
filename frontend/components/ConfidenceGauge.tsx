"use client";

import { useEffect, useRef } from "react";

interface ConfidenceGaugeProps {
  confidence: number;
  direction: "CALL" | "PUT";
  size?: number;
}

function getColor(confidence: number): string {
  if (confidence >= 70) return "#00d4aa";
  if (confidence >= 50) return "#f59e0b";
  return "#ff3b5c";
}

function getLabel(confidence: number): string {
  if (confidence >= 75) return "High Confidence";
  if (confidence >= 55) return "Watch";
  return "Low Signal";
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const x1 = cx + r * Math.cos(toRad(startAngle));
  const y1 = cy + r * Math.sin(toRad(startAngle));
  const x2 = cx + r * Math.cos(toRad(endAngle));
  const y2 = cy + r * Math.sin(toRad(endAngle));
  const largeArcFlag = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArcFlag} 1 ${x2} ${y2}`;
}

export default function ConfidenceGauge({ confidence, direction, size = 160 }: ConfidenceGaugeProps) {
  const clampedConf = Math.max(0, Math.min(100, confidence));
  const color = getColor(clampedConf);
  const label = getLabel(clampedConf);

  const cx = size / 2;
  const cy = size / 2 + size * 0.05;
  const r = size * 0.38;
  const strokeWidth = size * 0.07;

  // Semi-circle: 180° to 360° (left to right, bottom arc)
  const START_ANGLE = 180;
  const END_ANGLE = 360;

  // Fill from START_ANGLE to angle based on confidence
  const fillAngle = START_ANGLE + (clampedConf / 100) * 180;

  const bgPath = describeArc(cx, cy, r, START_ANGLE, END_ANGLE);
  const fillPath = clampedConf > 0 ? describeArc(cx, cy, r, START_ANGLE, fillAngle) : "";

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`} overflow="visible">
        {/* Background track */}
        <path
          d={bgPath}
          fill="none"
          stroke="#1e2029"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Colored fill */}
        {fillPath && (
          <path
            d={fillPath}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.6s ease, stroke 0.4s ease" }}
          />
        )}
        {/* Center: confidence number */}
        <text
          x={cx}
          y={cy + size * 0.01}
          textAnchor="middle"
          fill="#f0f2f5"
          fontSize={size * 0.2}
          fontWeight="700"
          fontFamily="-apple-system, sans-serif"
        >
          {Math.round(clampedConf)}
        </text>
        {/* Sub-text: direction */}
        <text
          x={cx}
          y={cy + size * 0.13}
          textAnchor="middle"
          fill={color}
          fontSize={size * 0.1}
          fontWeight="600"
          fontFamily="-apple-system, sans-serif"
          letterSpacing="1"
        >
          {direction}
        </text>
        {/* 0 label */}
        <text
          x={cx - r - strokeWidth / 2}
          y={cy + size * 0.05}
          textAnchor="middle"
          fill="#6b7280"
          fontSize={size * 0.08}
          fontFamily="-apple-system, sans-serif"
        >
          0
        </text>
        {/* 100 label */}
        <text
          x={cx + r + strokeWidth / 2}
          y={cy + size * 0.05}
          textAnchor="middle"
          fill="#6b7280"
          fontSize={size * 0.08}
          fontFamily="-apple-system, sans-serif"
        >
          100
        </text>
      </svg>
      <div
        className="mt-1 text-xs font-medium px-2 py-0.5 rounded-full"
        style={{
          color,
          background: `${color}20`,
          border: `1px solid ${color}40`,
        }}
      >
        {label}
      </div>
    </div>
  );
}
