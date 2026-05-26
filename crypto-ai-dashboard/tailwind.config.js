/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f1e3",
          100: "#efe4cd",
          200: "#d8c9ad",
          300: "#a99f8a",
          400: "#7e7666",
          500: "#5d564b",
        },
        surface: {
          990: "#030303",
          950: "#050505",
          925: "#090806",
          900: "#0b0b0a",
          850: "#11100d",
          800: "#15120d",
          750: "#1d1810",
          700: "#282116",
        },
        line: {
          soft: "rgba(216, 180, 90, 0.12)",
          strong: "rgba(216, 180, 90, 0.28)",
          cool: "rgba(247, 241, 227, 0.08)",
        },
        accent: {
          gold: "#d8b45a",
          goldSoft: "#b88a2e",
          champagne: "#ead8a4",
          bronze: "#7c5a1e",
          green: "#20c997",
          red: "#e35d5b",
          slate: "#9c927d",
        },
      },
      boxShadow: {
        glow: "0 0 34px rgba(216, 180, 90, 0.16)",
        panel: "0 24px 70px rgba(0, 0, 0, 0.46)",
        lift: "0 18px 45px rgba(0, 0, 0, 0.34), 0 0 22px rgba(216, 180, 90, 0.08)",
      },
      fontFamily: {
        sans: ["Plus Jakarta Sans", "Geist", "Aptos", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Consolas", "monospace"],
      },
      transitionTimingFunction: {
        premium: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
    },
  },
  plugins: [],
};
