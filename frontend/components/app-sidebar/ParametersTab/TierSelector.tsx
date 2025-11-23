"use client";

import * as React from "react";
import { Star } from "lucide-react";

interface TierSelectorProps {
  tier: number;
  onChange: (tier: number) => void;
  maxTier?: number;
}

const TIER_COLORS = [
  "rgb(107, 114, 128)",  // gray-500 for tier 0
  "rgb(34, 197, 94)",    // green-500
  "rgb(59, 130, 246)",   // blue-500
  "rgb(168, 85, 247)",   // purple-500
  "rgb(239, 68, 68)",    // red-500 for tier 4
];

export function TierSelector({ tier, onChange, maxTier = 4 }: TierSelectorProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const nextTier = tier >= maxTier ? 0 : tier + 1;
    onChange(nextTier);
  };

  const color = TIER_COLORS[tier] || TIER_COLORS[0];

  return (
    <button
      onClick={handleClick}
      className="shrink-0 transition-all hover:scale-110 flex items-center gap-0.5 relative z-20 cursor-pointer"
      title={tier === 0 ? "Click to set priority tier" : `Tier ${tier} - Click to change`}
    >
      <Star
        className="w-3.5 h-3.5"
        style={{
          color,
          fill: tier > 0 ? color : "none",
          strokeWidth: 2,
        }}
      />
      {tier > 0 && (
        <span
          className="text-[10px] font-semibold tabular-nums"
          style={{ color }}
        >
          {tier}
        </span>
      )}
    </button>
  );
}
