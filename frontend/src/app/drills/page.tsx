"use client";

import { FlashCard } from "@/components/FlashCard";
import { useSRS } from "@/hooks/useSRS";

export default function DrillsPage() {
  const {
    currentCard,
    currentIndex,
    cards,
    stats,
    isLoading,
    isFlipped,
    isComplete,
    flip,
    review,
    reload,
  } = useSRS();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        読み込み中...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">フラッシュカード</h1>
        {stats && (
          <span className="text-sm text-gray-400">
            本日 {stats.due_count} 枚
          </span>
        )}
      </div>

      {/* Box distribution */}
      {stats && (
        <div className="flex gap-1 h-2">
          {[1, 2, 3, 4, 5].map((box) => {
            const count = stats.box_distribution[String(box)] ?? 0;
            const total = stats.total_cards || 1;
            return (
              <div
                key={box}
                className="rounded-full bg-aki-purple"
                style={{ flex: count / total, minWidth: count > 0 ? 4 : 0 }}
                title={`Box ${box}: ${count}枚`}
              />
            );
          })}
        </div>
      )}

      {isComplete ? (
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="text-4xl">🎉</div>
          <p className="text-lg font-bold text-white">今日のドリル完了！</p>
          {stats && (
            <p className="text-sm text-gray-400">
              正解率 {Math.round(stats.accuracy_rate * 100)}% · Box5 卒業 {stats.graduated_this_week} 枚/週
            </p>
          )}
          <button
            onClick={reload}
            className="mt-4 px-6 py-2 bg-aki-blue rounded-full text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            再読み込み
          </button>
        </div>
      ) : (
        <>
          {/* Progress */}
          <div className="flex items-center gap-3">
            <div className="flex-1 bg-gray-700 rounded-full h-1.5">
              <div
                className="bg-aki-blue rounded-full h-1.5 transition-all"
                style={{ width: `${((currentIndex + 1) / cards.length) * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">
              {currentIndex + 1}/{cards.length}
            </span>
          </div>

          {currentCard && (
            <FlashCard
              card={currentCard}
              isFlipped={isFlipped}
              onFlip={flip}
            />
          )}

          {isFlipped && (
            <div className="flex gap-4 justify-center mt-4">
              <button
                onClick={() => review(false)}
                className="flex-1 max-w-32 py-3 bg-red-700 hover:bg-red-600 rounded-xl font-medium transition-colors"
              >
                ✗ 間違い
              </button>
              <button
                onClick={() => review(true)}
                className="flex-1 max-w-32 py-3 bg-green-700 hover:bg-green-600 rounded-xl font-medium transition-colors"
              >
                ✓ 正解
              </button>
            </div>
          )}

          {!isFlipped && (
            <p className="text-center text-sm text-gray-500">
              カードをタップして答えを確認
            </p>
          )}
        </>
      )}
    </div>
  );
}
