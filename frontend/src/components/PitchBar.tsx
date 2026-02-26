"use client";

interface PitchBarProps {
  morae: string[];
  pattern: number[];       // 0=low, 1=high, 2=falling
  mismatches?: number[];   // indices of mismatched morae (from compare)
  showMorae?: boolean;
}

const PATTERN_COLORS = {
  0: "bg-gray-500",    // low
  1: "bg-green-500",   // high
  2: "bg-orange-500",  // falling
};

const MISMATCH_COLOR = "bg-red-500";

const PATTERN_HEIGHTS = {
  0: "h-2",    // low — thin bar at bottom
  1: "h-8",   // high — tall bar
  2: "h-5",   // falling — medium
};

export function PitchBar({ morae, pattern, mismatches = [], showMorae = true }: PitchBarProps) {
  if (morae.length === 0) {
    return (
      <div className="text-xs text-gray-500 italic">ピッチデータなし</div>
    );
  }

  return (
    <div className="flex items-end gap-1">
      {morae.map((mora, i) => {
        const level = pattern[i] ?? 0;
        const isMismatch = mismatches.includes(i);
        const colorClass = isMismatch ? MISMATCH_COLOR : PATTERN_COLORS[level as keyof typeof PATTERN_COLORS] ?? PATTERN_COLORS[0];
        const heightClass = PATTERN_HEIGHTS[level as keyof typeof PATTERN_HEIGHTS] ?? PATTERN_HEIGHTS[0];

        return (
          <div key={i} className="flex flex-col items-center gap-0.5">
            <div className={`w-6 rounded-sm ${heightClass} ${colorClass} transition-all`} />
            {showMorae && (
              <span className="text-xs font-japanese text-gray-300">{mora}</span>
            )}
          </div>
        );
      })}
      <div className="ml-2 flex flex-col gap-1 text-xs text-gray-500 self-end">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 bg-green-500 rounded" /> 高
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-2 bg-gray-500 rounded" /> 低
        </span>
        {mismatches.length > 0 && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 bg-red-500 rounded" /> 誤
          </span>
        )}
      </div>
    </div>
  );
}
