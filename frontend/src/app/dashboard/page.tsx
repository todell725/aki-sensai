"use client";

import { useEffect, useState } from "react";
import { getMetrics, getDrillStats, type MetricsResponse, type DrillStats } from "@/lib/api";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [srsStats, setSrsStats] = useState<DrillStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([getMetrics(), getDrillStats()])
      .then(([m, s]) => {
        setMetrics(m);
        setSrsStats(s);
      })
      .catch(console.error)
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400">
        読み込み中...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold">学習記録</h1>

      {/* Overview cards */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          value={metrics?.total_sessions ?? 0}
          label="総セッション"
          unit="回"
        />
        <StatCard
          value={Math.round((metrics?.productive_ratio ?? 0) * 100)}
          label="プロダクティブ比率"
          unit="%"
          highlight={
            (metrics?.productive_ratio ?? 0) >= 0.6 ? "good" : "warn"
          }
        />
        <StatCard
          value={Math.round(metrics?.avg_session_duration_s ?? 0)}
          label="平均セッション時間"
          unit="秒"
        />
        <StatCard
          value={srsStats?.total_cards ?? 0}
          label="SRS総カード"
          unit="枚"
        />
      </div>

      {/* SRS Box distribution */}
      {srsStats && (
        <div className="bg-gray-800 rounded-xl p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">SRS ボックス分布</h2>
          <div className="flex items-end gap-2 h-24">
            {[1, 2, 3, 4, 5].map((box) => {
              const count = srsStats.box_distribution[String(box)] ?? 0;
              const maxCount = Math.max(
                ...Object.values(srsStats.box_distribution).map(Number),
                1,
              );
              const heightPct = (count / maxCount) * 100;
              const colors = [
                "bg-red-500",
                "bg-orange-500",
                "bg-yellow-500",
                "bg-blue-500",
                "bg-green-500",
              ];
              return (
                <div key={box} className="flex flex-col items-center gap-1 flex-1">
                  <span className="text-xs text-gray-400">{count}</span>
                  <div
                    className={`w-full rounded-t ${colors[box - 1]} transition-all`}
                    style={{ height: `${heightPct}%`, minHeight: count > 0 ? 4 : 0 }}
                  />
                  <span className="text-xs text-gray-500">B{box}</span>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex justify-between text-xs text-gray-500">
            <span>正解率 {Math.round(srsStats.accuracy_rate * 100)}%</span>
            <span>今週卒業 {srsStats.graduated_this_week}枚</span>
          </div>
        </div>
      )}

      {/* Productive struggle trend */}
      {metrics && metrics.recent_sessions.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            プロダクティブ比率 (直近30日)
          </h2>
          <div className="flex items-end gap-0.5 h-20">
            {metrics.recent_sessions.slice(0, 30).reverse().map((s, i) => {
              const ratio = s.productive_ratio;
              return (
                <div
                  key={i}
                  className="flex-1 rounded-t bg-aki-purple opacity-80"
                  style={{ height: `${ratio * 100}%`, minHeight: 2 }}
                  title={`${s.date?.slice(0, 10)}: ${Math.round(ratio * 100)}%`}
                />
              );
            })}
          </div>
          <div className="mt-1 text-xs text-gray-500 text-right">
            目標: 60%+
          </div>
        </div>
      )}

      {/* Top failure patterns */}
      {metrics && metrics.top_failure_patterns.length > 0 && (
        <div className="bg-gray-800 rounded-xl p-4">
          <h2 className="text-sm font-semibold text-gray-300 mb-3">
            よくある誤りパターン
          </h2>
          <ul className="flex flex-col gap-2">
            {metrics.top_failure_patterns.map((p, i) => (
              <li key={i} className="flex items-center justify-between text-sm">
                <span className="text-gray-300 font-japanese">{p.pattern}</span>
                <span className="text-gray-500">{p.count}回</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function StatCard({
  value,
  label,
  unit,
  highlight,
}: {
  value: number;
  label: string;
  unit: string;
  highlight?: "good" | "warn";
}) {
  const valueColor =
    highlight === "good"
      ? "text-green-400"
      : highlight === "warn"
      ? "text-yellow-400"
      : "text-white";

  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center">
      <div className={`text-3xl font-bold ${valueColor}`}>
        {value}
        <span className="text-lg font-normal text-gray-400">{unit}</span>
      </div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  );
}
