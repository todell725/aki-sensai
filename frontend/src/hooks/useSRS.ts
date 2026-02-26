"use client";

import { useCallback, useEffect, useState } from "react";
import { getDueCards, reviewCard, getDrillStats, type SRSCard, type DrillStats } from "@/lib/api";

export function useSRS() {
  const [cards, setCards] = useState<SRSCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [stats, setStats] = useState<DrillStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isFlipped, setIsFlipped] = useState(false);

  const loadDueCards = useCallback(async () => {
    setIsLoading(true);
    try {
      const due = await getDueCards();
      setCards(due);
      setCurrentIndex(0);
      setIsFlipped(false);
    } catch (err) {
      console.error("Failed to load due cards:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      const s = await getDrillStats();
      setStats(s);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  }, []);

  const flip = useCallback(() => setIsFlipped((v) => !v), []);

  const review = useCallback(
    async (correct: boolean) => {
      const card = cards[currentIndex];
      if (!card) return;

      try {
        await reviewCard(card.id, correct);
      } catch (err) {
        console.error("Failed to review card:", err);
      }

      if (currentIndex + 1 >= cards.length) {
        // Session complete
        await loadDueCards();
        await loadStats();
      } else {
        setCurrentIndex((i) => i + 1);
        setIsFlipped(false);
      }
    },
    [cards, currentIndex, loadDueCards, loadStats],
  );

  useEffect(() => {
    loadDueCards();
    loadStats();
  }, [loadDueCards, loadStats]);

  const currentCard = cards[currentIndex] ?? null;
  const isComplete = cards.length === 0 || currentIndex >= cards.length;

  return {
    currentCard,
    cards,
    currentIndex,
    stats,
    isLoading,
    isFlipped,
    isComplete,
    flip,
    review,
    reload: loadDueCards,
  };
}
