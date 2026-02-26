"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getVoiceWsUrl } from "@/lib/api";

export interface LatencyReport {
  vad_ms: number;
  stt_ms: number;
  llm_ttft_ms: number;
  tts_ms: number;
  total_ms: number;
}

export interface TranscriptTurn {
  role: "user" | "assistant";
  text: string;
}

interface UseVoiceStreamOptions {
  toneMode: string;
  grammarLevel: string;
  task?: string;
  onTranscript?: (text: string) => void;
  onLatency?: (report: LatencyReport) => void;
  onError?: (msg: string) => void;
}

export function useVoiceStream({
  toneMode,
  grammarLevel,
  task = "free_conversation",
  onTranscript,
  onLatency,
  onError,
}: UseVoiceStreamOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);

  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [turns, setTurns] = useState<TranscriptTurn[]>([]);

  const getAudioCtx = useCallback((): AudioContext => {
    if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
      audioCtxRef.current = new AudioContext({ sampleRate: 22050 });
    }
    if (audioCtxRef.current.state === "suspended") {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }, []);

  const playWavChunk = useCallback(async (wavBytes: ArrayBuffer) => {
    try {
      const ctx = getAudioCtx();
      const audioBuffer = await ctx.decodeAudioData(wavBytes.slice(0));
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);

      const startTime = Math.max(ctx.currentTime, nextPlayTimeRef.current);
      source.start(startTime);
      nextPlayTimeRef.current = startTime + audioBuffer.duration;

      setIsPlaying(true);
      source.onended = () => {
        if (nextPlayTimeRef.current <= ctx.currentTime) {
          setIsPlaying(false);
        }
      };
    } catch {
      // Decode error is non-fatal (e.g. partial WAV chunk)
    }
  }, [getAudioCtx]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(getVoiceWsUrl());
    wsRef.current = ws;
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      setIsConnected(true);
      // Send initial config
      ws.send(JSON.stringify({
        type: "config",
        tone_mode: toneMode,
        grammar_level: grammarLevel,
        task,
      }));
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsRecording(false);
    };

    ws.onerror = () => {
      onError?.("WebSocket connection failed");
    };

    ws.onmessage = async (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary: WAV audio chunk
        await playWavChunk(event.data);
        return;
      }

      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === "transcript") {
          onTranscript?.(msg.text);
          setTurns((prev) => [...prev, { role: "user", text: msg.text }]);
        } else if (msg.type === "tts_end") {
          setIsPlaying(false);
        } else if (msg.type === "latency") {
          onLatency?.(msg.data as LatencyReport);
        } else if (msg.type === "error") {
          onError?.(msg.text);
        }
      } catch {
        // Non-JSON text frame — ignore
      }
    };
  }, [toneMode, grammarLevel, task, onTranscript, onLatency, onError, playWavChunk]);

  const startRecording = useCallback(async () => {
    connect();

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Use ScriptProcessor to get raw PCM (AudioWorklet preferred but ScriptProcessor is universal)
      const ctx = getAudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState !== WebSocket.OPEN) return;
        const float32 = e.inputBuffer.getChannelData(0);
        // Convert float32 to int16
        const int16 = new Int16Array(float32.length);
        for (let i = 0; i < float32.length; i++) {
          int16[i] = Math.max(-32768, Math.min(32767, float32[i] * 32768));
        }
        wsRef.current.send(int16.buffer);
      };

      source.connect(processor);
      processor.connect(ctx.destination);

      mediaRecorderRef.current = {
        stop: () => {
          processor.disconnect();
          source.disconnect();
          stream.getTracks().forEach((t) => t.stop());
        },
      } as unknown as MediaRecorder;

      setIsRecording(true);
    } catch (err) {
      onError?.("Microphone access denied");
    }
  }, [connect, getAudioCtx, onError]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      (mediaRecorderRef.current as unknown as { stop: () => void }).stop();
      mediaRecorderRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setIsRecording(false);
  }, []);

  const disconnect = useCallback(() => {
    stopRecording();
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, [stopRecording]);

  // Send config update when tone/level changes
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "config",
        tone_mode: toneMode,
        grammar_level: grammarLevel,
        task,
      }));
    }
  }, [toneMode, grammarLevel, task]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isRecording,
    isPlaying,
    turns,
    startRecording,
    stopRecording,
    disconnect,
    connect,
  };
}
