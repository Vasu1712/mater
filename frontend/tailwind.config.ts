import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0f17",
        panel: "#131a26",
        accent: "#34d399",
        warn: "#fbbf24",
        crit: "#f87171",
      },
    },
  },
  plugins: [],
};

export default config;
