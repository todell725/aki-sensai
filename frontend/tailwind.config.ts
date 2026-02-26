import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "aki-purple": "#7C3AED",
        "aki-blue": "#2563EB",
        "aki-red": "#DC2626",
        "aki-green": "#16A34A",
      },
      fontFamily: {
        japanese: ["Noto Sans JP", "Hiragino Sans", "Yu Gothic", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "bounce-subtle": "bounce 1s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
