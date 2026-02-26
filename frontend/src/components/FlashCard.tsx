"use client";

import type { SRSCard } from "@/lib/api";

const AFFECT_COLORS: Record<string, string> = {
  masculine_assertion: "bg-orange-600",
  feminine_soft: "bg-pink-500",
  casual: "bg-yellow-600",
  hearsay: "bg-teal-600",
  casual_masculine: "bg-amber-600",
  clipped: "bg-red-700",
  neutral: "bg-gray-600",
};

const AFFECT_LABELS: Record<string, string> = {
  masculine_assertion: "男性語",
  feminine_soft: "女性語",
  casual: "カジュアル",
  hearsay: "伝聞",
  casual_masculine: "カジュアル男性",
  clipped: "省略形",
  neutral: "標準",
};

interface FlashCardProps {
  card: SRSCard;
  isFlipped: boolean;
  onFlip: () => void;
}

export function FlashCard({ card, isFlipped, onFlip }: FlashCardProps) {
  const affectColor = AFFECT_COLORS[card.affect_tag ?? "neutral"] ?? AFFECT_COLORS.neutral;
  const affectLabel = AFFECT_LABELS[card.affect_tag ?? "neutral"] ?? "標準";

  return (
    <div
      className="relative w-full max-w-sm mx-auto cursor-pointer select-none"
      style={{ perspective: "1000px" }}
      onClick={onFlip}
    >
      <div
        className="relative w-full transition-transform duration-500"
        style={{
          transformStyle: "preserve-3d",
          transform: isFlipped ? "rotateY(180deg)" : "rotateY(0deg)",
          minHeight: "220px",
        }}
      >
        {/* Front */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-800 rounded-2xl p-6 shadow-xl"
          style={{ backfaceVisibility: "hidden" }}
        >
          <div className="text-5xl font-japanese font-bold text-white mb-3">
            {card.lemma}
          </div>
          {card.jlpt_level && (
            <span className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded">
              {card.jlpt_level}
            </span>
          )}
          {card.affect_tag && card.affect_tag !== "neutral" && (
            <span className={`mt-2 text-xs ${affectColor} text-white px-2 py-1 rounded`}>
              {affectLabel}
            </span>
          )}
          <p className="mt-4 text-xs text-gray-500">タップして答えを見る</p>
        </div>

        {/* Back */}
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-gray-700 rounded-2xl p-6 shadow-xl"
          style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
        >
          {card.reading && (
            <div className="text-sm text-gray-400 mb-1 font-japanese">{card.reading}</div>
          )}
          <div className="text-2xl font-bold text-white mb-3 font-japanese text-center">
            {card.meaning ?? "意味不明"}
          </div>
          {card.example_sentence && (
            <div className="text-sm text-gray-300 font-japanese text-center italic border-t border-gray-600 pt-3 mt-1">
              {card.example_sentence}
            </div>
          )}
          {card.frequency > 1 && (
            <div className="mt-2 text-xs text-gray-500">
              出現 {card.frequency} 回 · Box {card.box}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
