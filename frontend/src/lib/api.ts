const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

// ── Types ─────────────────────────────────────────────────────────────────────

export interface VocabEntry {
  lemma: string;
  reading?: string;
  meaning?: string;
  jlpt_level?: string;
  frequency: number;
  affect_tag?: string;
  example_sentence?: string;
}

export interface SRSCard {
  id: number;
  show_id?: string;
  lemma: string;
  reading?: string;
  meaning?: string;
  jlpt_level?: string;
  frequency: number;
  box: number;
  next_review: string;
  exposures: number;
  correct_count: number;
  wrong_count: number;
  affect_tag?: string;
  example_sentence?: string;
}

export interface DrillStats {
  box_distribution: Record<string, number>;
  total_cards: number;
  accuracy_rate: number;
  graduated_this_week: number;
  due_count: number;
}

export interface SubtitleUploadResponse {
  show_id: string;
  show_name: string;
  total_lines: number;
  unique_lemmas: number;
  top_vocab: VocabEntry[];
}

export interface PitchContour {
  text: string;
  morae: string[];
  pattern: number[];
}

export interface PitchCompareResponse {
  match_ratio: number;
  mismatched_morae: number[];
  reference_pattern: number[];
  attempt_pattern: number[];
}

export interface MetricsResponse {
  total_sessions: number;
  total_turns: number;
  productive_ratio: number;
  avg_session_duration_s: number;
  recent_sessions: Array<{
    date: string;
    turn_count: number;
    productive_turns: number;
    productive_ratio: number;
    duration_s: number;
  }>;
  top_failure_patterns: Array<{ pattern: string; count: number }>;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path}: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export async function streamChat(
  message: string,
  toneMode: string,
  grammarLevel: string,
  task: string,
  onToken: (token: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, tone_mode: toneMode, grammar_level: grammarLevel, task }),
  });

  if (!res.ok || !res.body) throw new Error("Chat stream failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onToken(decoder.decode(value, { stream: true }));
  }
}

export async function speak(text: string): Promise<ArrayBuffer> {
  const res = await fetch(`${API_BASE}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error("TTS synthesis failed");
  return res.arrayBuffer();
}

// ── Pitch ─────────────────────────────────────────────────────────────────────

export async function analyzePitch(text: string): Promise<PitchContour> {
  return apiFetch<PitchContour>("/pitch/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

// ── Drills / SRS ──────────────────────────────────────────────────────────────

export async function getDueCards(): Promise<SRSCard[]> {
  return apiFetch<SRSCard[]>("/drills/due");
}

export async function reviewCard(cardId: number, correct: boolean): Promise<SRSCard> {
  return apiFetch<SRSCard>(`/drills/${cardId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ correct }),
  });
}

export async function getDrillStats(): Promise<DrillStats> {
  return apiFetch<DrillStats>("/drills/stats");
}

export async function getShadowingLines(
  showId: string,
  limit = 5,
): Promise<Array<{ card_id: number; lemma: string; sentence: string; affect_tag?: string }>> {
  return apiFetch(`/drills/shadowing/${showId}?limit=${limit}`);
}

// ── Subtitles ─────────────────────────────────────────────────────────────────

export async function uploadSubtitles(
  file: File,
  showName: string,
): Promise<SubtitleUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("show_name", showName);

  const res = await fetch(`${API_BASE}/subtitles/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Subtitle upload failed");
  return res.json();
}

export async function getVocab(showId: string, limit = 50): Promise<VocabEntry[]> {
  return apiFetch<VocabEntry[]>(`/subtitles/${showId}/vocab?limit=${limit}`);
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export async function getMetrics(): Promise<MetricsResponse> {
  return apiFetch<MetricsResponse>("/metrics");
}

// ── WebSocket URL helper ──────────────────────────────────────────────────────

export function getVoiceWsUrl(): string {
  return `${WS_BASE}/ws/voice`;
}
