"use client";

interface MicButtonProps {
  isRecording: boolean;
  isPlaying: boolean;
  isConnected: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function MicButton({
  isRecording,
  isPlaying,
  isConnected,
  onStart,
  onStop,
}: MicButtonProps) {
  const handleClick = () => {
    if (isRecording) {
      onStop();
    } else {
      onStart();
    }
  };

  const getState = () => {
    if (isPlaying) return "playing";
    if (isRecording) return "recording";
    return "idle";
  };

  const state = getState();

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        onClick={handleClick}
        disabled={isPlaying}
        className={`
          w-24 h-24 rounded-full flex items-center justify-center
          text-white font-bold text-2xl shadow-lg
          transition-all duration-200 active:scale-95
          ${state === "recording"
            ? "bg-aki-red animate-pulse-slow scale-110"
            : state === "playing"
            ? "bg-aki-purple cursor-not-allowed"
            : "bg-aki-blue hover:bg-blue-700"
          }
        `}
        aria-label={isRecording ? "録音停止" : "録音開始"}
      >
        {state === "recording" ? "■" : state === "playing" ? "♪" : "🎤"}
      </button>

      <span className="text-sm text-gray-400">
        {state === "recording"
          ? "話してください..."
          : state === "playing"
          ? "アキ先生が話しています"
          : isConnected
          ? "タップして話す"
          : "接続中..."}
      </span>
    </div>
  );
}
