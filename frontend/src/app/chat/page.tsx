"use client";

import { useCallback, useState } from "react";
import { MicButton } from "@/components/MicButton";
import { ToneToggle } from "@/components/ToneToggle";
import { useVoiceStream, type LatencyReport } from "@/hooks/useVoiceStream";

const GRAMMAR_LEVELS = ["N5", "N4", "N3", "N2", "N1"];

export default function ChatPage() {
  const [toneMode, setToneMode] = useState<"textbook" | "anime">("textbook");
  const [grammarLevel, setGrammarLevel] = useState("N5");
  const [lastLatency, setLastLatency] = useState<LatencyReport | null>(null);
  const [productiveTurns, setProductiveTurns] = useState(0);
  const [totalTurns, setTotalTurns] = useState(0);

  const handleTranscript = useCallback(() => {
    setTotalTurns((n) => n + 1);
  }, []);

  const handleLatency = useCallback((report: LatencyReport) => {
    setLastLatency(report);
    if (report.total_ms < 15000) {
      setProductiveTurns((n) => n + 1);
    }
  }, []);

  const {
    isConnected,
    isRecording,
    isPlaying,
    turns,
    startRecording,
    stopRecording,
  } = useVoiceStream({
    toneMode,
    grammarLevel,
    task: "free_conversation",
    onTranscript: handleTranscript,
    onLatency: handleLatency,
  });

  const productiveRatio =
    totalTurns > 0 ? Math.round((productiveTurns / totalTurns) * 100) : 0;

  return (
    <div className="flex flex-col gap-6">
      {/* Controls */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <ToneToggle toneMode={toneMode} onChange={setToneMode} />
        <select
          value={grammarLevel}
          onChange={(e) => setGrammarLevel(e.target.value)}
          className="bg-gray-800 text-white text-sm rounded-lg px-3 py-1.5 border border-gray-700"
        >
          {GRAMMAR_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>

      {/* Transcript history */}
      <div className="flex flex-col gap-3 min-h-48 max-h-80 overflow-y-auto">
        {turns.length === 0 ? (
          <p className="text-gray-500 text-sm text-center mt-8">
            アキ先生と話してみましょう
          </p>
        ) : (
          turns.map((turn, i) => (
            <div
              key={i}
              className={`max-w-xs px-4 py-2 rounded-2xl text-sm font-japanese ${
                turn.role === "user"
                  ? "self-end bg-aki-blue text-white"
                  : "self-start bg-gray-700 text-gray-100"
              }`}
            >
              {turn.text}
            </div>
          ))
        )}
      </div>

      {/* Mic button */}
      <div className="flex justify-center py-4">
        <MicButton
          isRecording={isRecording}
          isPlaying={isPlaying}
          isConnected={isConnected}
          onStart={startRecording}
          onStop={stopRecording}
        />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 text-center">
        <div className="bg-gray-800 rounded-xl p-3">
          <div className="text-2xl font-bold text-white">{productiveRatio}%</div>
          <div className="text-xs text-gray-400">プロダクティブ比率</div>
        </div>
        <div className="bg-gray-800 rounded-xl p-3">
          <div className="text-2xl font-bold text-white">
            {lastLatency ? `${Math.round(lastLatency.total_ms)}ms` : "—"}
          </div>
          <div className="text-xs text-gray-400">応答レイテンシ</div>
        </div>
      </div>

      {/* Latency breakdown */}
      {lastLatency && (
        <div className="bg-gray-800 rounded-xl p-4 text-xs text-gray-400 grid grid-cols-4 gap-2 text-center">
          <div>
            <div className="text-white font-mono">{Math.round(lastLatency.vad_ms)}ms</div>
            <div>VAD</div>
          </div>
          <div>
            <div className="text-white font-mono">{Math.round(lastLatency.stt_ms)}ms</div>
            <div>STT</div>
          </div>
          <div>
            <div className="text-white font-mono">{Math.round(lastLatency.llm_ttft_ms)}ms</div>
            <div>LLM</div>
          </div>
          <div>
            <div className="text-white font-mono">{Math.round(lastLatency.tts_ms)}ms</div>
            <div>TTS</div>
          </div>
        </div>
      )}
    </div>
  );
}
