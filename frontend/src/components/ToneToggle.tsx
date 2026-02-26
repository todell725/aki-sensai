"use client";

interface ToneToggleProps {
  toneMode: "textbook" | "anime";
  onChange: (mode: "textbook" | "anime") => void;
}

export function ToneToggle({ toneMode, onChange }: ToneToggleProps) {
  return (
    <div className="flex items-center gap-1 bg-gray-800 rounded-full p-1">
      <button
        onClick={() => onChange("textbook")}
        className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
          toneMode === "textbook"
            ? "bg-aki-blue text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        教科書
      </button>
      <button
        onClick={() => onChange("anime")}
        className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
          toneMode === "anime"
            ? "bg-aki-purple text-white"
            : "text-gray-400 hover:text-white"
        }`}
      >
        アニメ
      </button>
    </div>
  );
}
