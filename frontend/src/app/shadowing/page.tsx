"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PitchBar } from "@/components/PitchBar";
import { getShadowingLines, analyzePitch, type PitchContour, type PitchCompareResponse } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Decode any browser-recorded audio blob (webm/opus, ogg, wav…) via AudioContext,
 * then re-encode as a 16kHz mono 16-bit WAV that librosa/soundfile can read reliably.
 */
async function normalizeToWav(blob: Blob): Promise<Blob> {
  const arrayBuf = await blob.arrayBuffer();
  const ctx = new AudioContext({ sampleRate: 16000 });
  let audioBuffer: AudioBuffer;
  try {
    audioBuffer = await ctx.decodeAudioData(arrayBuf);
  } finally {
    await ctx.close();
  }

  // Mix down to mono and resample to 16 kHz (AudioContext handles resampling)
  const samples = audioBuffer.getChannelData(0);
  const numSamples = samples.length;

  // WAV header: RIFF/PCM 16-bit mono
  const byteLength = 44 + numSamples * 2;
  const buffer = new ArrayBuffer(byteLength);
  const view = new DataView(buffer);

  const writeStr = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  };
  writeStr(0, "RIFF");
  view.setUint32(4, byteLength - 8, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);       // chunk size
  view.setUint16(20, 1, true);        // PCM
  view.setUint16(22, 1, true);        // mono
  view.setUint32(24, 16000, true);    // sample rate
  view.setUint32(28, 16000 * 2, true); // byte rate
  view.setUint16(32, 2, true);        // block align
  view.setUint16(34, 16, true);       // bits per sample
  writeStr(36, "data");
  view.setUint32(40, numSamples * 2, true);

  let offset = 44;
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    offset += 2;
  }

  return new Blob([buffer], { type: "audio/wav" });
}

interface ShadowingLine {
  card_id: number;
  lemma: string;
  sentence: string;
  affect_tag?: string;
}

export default function ShadowingPage() {
  const [showId, setShowId] = useState("");
  const [lines, setLines] = useState<ShadowingLine[]>([]);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [referenceContour, setReferenceContour] = useState<PitchContour | null>(null);
  const [compareResult, setCompareResult] = useState<PitchCompareResponse | null>(null);
  const [userTranscript, setUserTranscript] = useState("");
  const [error, setError] = useState("");

  const audioCtxRef = useRef<AudioContext | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const currentLine = lines[currentIdx];

  const loadLines = async () => {
    if (!showId.trim()) return;
    try {
      const data = await getShadowingLines(showId, 10);
      setLines(data);
      setCurrentIdx(0);
      setCompareResult(null);
      setUserTranscript("");
    } catch {
      setError("字幕データの読み込みに失敗しました");
    }
  };

  const playReference = async () => {
    if (!currentLine) return;
    setIsPlaying(true);
    setCompareResult(null);

    try {
      const res = await fetch(`${API_BASE}/drills/shadowing/${currentLine.card_id}/speak`);
      if (!res.ok) throw new Error("TTS failed");
      const wavBuf = await res.arrayBuffer();

      if (!audioCtxRef.current) audioCtxRef.current = new AudioContext();
      const ctx = audioCtxRef.current;
      const decoded = await ctx.decodeAudioData(wavBuf.slice(0));
      const source = ctx.createBufferSource();
      source.buffer = decoded;
      source.connect(ctx.destination);
      source.start();
      source.onended = () => setIsPlaying(false);

      // Also fetch pitch contour for reference
      const contour = await analyzePitch(currentLine.sentence);
      setReferenceContour(contour);
    } catch {
      setError("音声の再生に失敗しました");
      setIsPlaying(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Prefer WAV if the browser supports it; fall back to whatever is available.
      const mimeType = MediaRecorder.isTypeSupported("audio/wav")
        ? "audio/wav"
        : MediaRecorder.isTypeSupported("audio/webm;codecs=pcm")
        ? "audio/webm;codecs=pcm"
        : "";
      const mr = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunksRef.current = [];

      mr.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        const nativeBlob = new Blob(audioChunksRef.current, { type: mr.mimeType });
        stream.getTracks().forEach((t) => t.stop());
        // Normalize to WAV via AudioContext so the backend always receives PCM audio
        const wavBlob = await normalizeToWav(nativeBlob);
        await submitAttempt(wavBlob);
      };

      mr.start();
      mediaRecorderRef.current = mr;
      setIsRecording(true);
    } catch {
      setError("マイクへのアクセスが拒否されました");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  const submitAttempt = async (wavBlob: Blob) => {
    if (!currentLine) return;
    try {
      const form = new FormData();
      form.append("audio_file", wavBlob, "attempt.wav");

      const res = await fetch(
        `${API_BASE}/drills/shadowing/${currentLine.card_id}/compare`,
        { method: "POST", body: form },
      );

      if (!res.ok) throw new Error("Compare failed");
      const result: PitchCompareResponse = await res.json();
      setCompareResult(result);
    } catch {
      setError("ピッチ比較に失敗しました");
    }
  };

  const nextLine = () => {
    setCurrentIdx((i) => Math.min(i + 1, lines.length - 1));
    setCompareResult(null);
    setReferenceContour(null);
    setUserTranscript("");
  };

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-bold">シャドーイング</h1>

      {/* Show ID input */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="ショーID を入力"
          value={showId}
          onChange={(e) => setShowId(e.target.value)}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white"
        />
        <button
          onClick={loadLines}
          className="px-4 py-2 bg-aki-blue rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          読込
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {lines.length === 0 ? (
        <p className="text-gray-500 text-sm text-center py-8">
          字幕ファイルをアップロードしてショーIDを入力してください
        </p>
      ) : currentLine ? (
        <div className="flex flex-col gap-5">
          {/* Progress */}
          <div className="text-xs text-gray-400 text-right">
            {currentIdx + 1}/{lines.length}
          </div>

          {/* Sentence display */}
          <div className="bg-gray-800 rounded-2xl p-5 text-center">
            <p className="text-2xl font-japanese text-white leading-relaxed">
              {currentLine.sentence}
            </p>
            {currentLine.affect_tag && (
              <span className="mt-2 inline-block text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded">
                {currentLine.affect_tag}
              </span>
            )}
          </div>

          {/* Reference pitch contour */}
          {referenceContour && referenceContour.morae.length > 0 && (
            <div className="bg-gray-800 rounded-xl p-4">
              <p className="text-xs text-gray-400 mb-3">参照ピッチ</p>
              <PitchBar
                morae={referenceContour.morae}
                pattern={referenceContour.pattern}
                mismatches={compareResult?.mismatched_morae ?? []}
              />
            </div>
          )}

          {/* Compare result */}
          {compareResult && (
            <div className="bg-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">ピッチ一致率</span>
                <span
                  className={`text-2xl font-bold ${
                    compareResult.match_ratio >= 0.7
                      ? "text-green-400"
                      : compareResult.match_ratio >= 0.5
                      ? "text-yellow-400"
                      : "text-red-400"
                  }`}
                >
                  {Math.round(compareResult.match_ratio * 100)}%
                </span>
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="flex gap-3 justify-center flex-wrap">
            <button
              onClick={playReference}
              disabled={isPlaying}
              className="px-5 py-2.5 bg-aki-purple hover:bg-purple-700 disabled:opacity-50 rounded-full text-sm font-medium transition-colors"
            >
              {isPlaying ? "再生中..." : "▶ 模範音声"}
            </button>

            {!isRecording ? (
              <button
                onClick={startRecording}
                disabled={isPlaying}
                className="px-5 py-2.5 bg-aki-red hover:bg-red-700 disabled:opacity-50 rounded-full text-sm font-medium transition-colors"
              >
                ● 録音
              </button>
            ) : (
              <button
                onClick={stopRecording}
                className="px-5 py-2.5 bg-gray-600 hover:bg-gray-500 rounded-full text-sm font-medium transition-colors animate-pulse"
              >
                ■ 停止
              </button>
            )}

            {currentIdx < lines.length - 1 && (
              <button
                onClick={nextLine}
                className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-full text-sm font-medium transition-colors"
              >
                次へ →
              </button>
            )}
          </div>
        </div>
      ) : (
        <p className="text-gray-500 text-center py-8">シャドーイング完了！</p>
      )}
    </div>
  );
}
