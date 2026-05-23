import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 20px 50px -28px rgb(15 23 42 / 0.35)"
      },
      colors: {
        brand: {
          50: "#fff7ed",
          100: "#fff1e8",
          500: "#ff5a00",
          600: "#e64f00",
          700: "#b83f00"
        }
      }
    }
  },
  plugins: []
} satisfies Config;

