import { create } from "zustand";

export interface ThemeDefinition {
  id: string;
  name: string;
  emoji: string;
  colors: {
    base: string;
    surface0: string;
    surface1: string;
    surface2: string;
    surface3: string;
    accent: string;
    accentBright: string;
    accentGhost: string;
    accentGlow: string;
    gradientActive: string;
    gradientHero: string;
    gradientSurface: string;
  };
}

export const themes: ThemeDefinition[] = [
  // ── Original 6 ──
  {
    id: "ultraviolet",
    name: "Ultraviolet",
    emoji: "\u{1F52E}",
    colors: {
      base: "#0a0a12",
      surface0: "#0c0c14",
      surface1: "#13131f",
      surface2: "#1a1a2a",
      surface3: "#242438",
      accent: "#6366f1",
      accentBright: "#a78bfa",
      accentGhost: "rgba(99,102,241,0.08)",
      accentGlow: "rgba(167,139,250,0.20)",
      gradientActive: "linear-gradient(135deg, #6366f1 0%, #a78bfa 50%, #c084fc 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #a78bfa 60%, #6366f1 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(99,102,241,0.04) 0%, transparent 60%)",
    },
  },
  {
    id: "midnight-ocean",
    name: "Midnight Ocean",
    emoji: "\u{1F30A}",
    colors: {
      base: "#060d14",
      surface0: "#0a1520",
      surface1: "#0f1d2c",
      surface2: "#152636",
      surface3: "#1c3044",
      accent: "#0ea5e9",
      accentBright: "#38bdf8",
      accentGhost: "rgba(14,165,233,0.08)",
      accentGlow: "rgba(56,189,248,0.20)",
      gradientActive: "linear-gradient(135deg, #0ea5e9 0%, #38bdf8 50%, #7dd3fc 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #38bdf8 60%, #0ea5e9 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(14,165,233,0.04) 0%, transparent 60%)",
    },
  },
  {
    id: "emerald-night",
    name: "Emerald Night",
    emoji: "\u{1F48E}",
    colors: {
      base: "#060f0a",
      surface0: "#0a1810",
      surface1: "#0f2118",
      surface2: "#152b20",
      surface3: "#1c382a",
      accent: "#10b981",
      accentBright: "#34d399",
      accentGhost: "rgba(16,185,129,0.08)",
      accentGlow: "rgba(52,211,153,0.20)",
      gradientActive: "linear-gradient(135deg, #10b981 0%, #34d399 50%, #6ee7b7 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #34d399 60%, #10b981 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(16,185,129,0.04) 0%, transparent 60%)",
    },
  },
  {
    id: "sunset-gold",
    name: "Sunset Gold",
    emoji: "\u{1F305}",
    colors: {
      base: "#0f0a06",
      surface0: "#18100a",
      surface1: "#21170f",
      surface2: "#2b1f15",
      surface3: "#38291c",
      accent: "#f59e0b",
      accentBright: "#fbbf24",
      accentGhost: "rgba(245,158,11,0.08)",
      accentGlow: "rgba(251,191,36,0.20)",
      gradientActive: "linear-gradient(135deg, #f59e0b 0%, #fbbf24 50%, #fde68a 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #fbbf24 60%, #f59e0b 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(245,158,11,0.04) 0%, transparent 60%)",
    },
  },
  {
    id: "rose-quartz",
    name: "Rose Quartz",
    emoji: "\u{1F339}",
    colors: {
      base: "#0f060a",
      surface0: "#180a10",
      surface1: "#210f18",
      surface2: "#2b1520",
      surface3: "#381c2a",
      accent: "#f43f5e",
      accentBright: "#fb7185",
      accentGhost: "rgba(244,63,94,0.08)",
      accentGlow: "rgba(251,113,133,0.20)",
      gradientActive: "linear-gradient(135deg, #f43f5e 0%, #fb7185 50%, #fda4af 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #fb7185 60%, #f43f5e 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(244,63,94,0.04) 0%, transparent 60%)",
    },
  },
  {
    id: "arctic-frost",
    name: "Arctic Frost",
    emoji: "\u{2744}\u{FE0F}",
    colors: {
      base: "#080a0f",
      surface0: "#0c1018",
      surface1: "#111821",
      surface2: "#18202c",
      surface3: "#202a38",
      accent: "#8b5cf6",
      accentBright: "#c4b5fd",
      accentGhost: "rgba(139,92,246,0.08)",
      accentGlow: "rgba(196,181,253,0.20)",
      gradientActive: "linear-gradient(135deg, #8b5cf6 0%, #c4b5fd 50%, #e0d5ff 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #c4b5fd 60%, #8b5cf6 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(139,92,246,0.04) 0%, transparent 60%)",
    },
  },

  // ── New dynamic themes ──
  {
    id: "neon-tokyo",
    name: "Neon Tokyo",
    emoji: "\u{1F3EE}",
    colors: {
      base: "#0a0008",
      surface0: "#12000f",
      surface1: "#1a0518",
      surface2: "#250a22",
      surface3: "#33102e",
      accent: "#ff2d95",
      accentBright: "#ff6eb4",
      accentGhost: "rgba(255,45,149,0.10)",
      accentGlow: "rgba(255,110,180,0.25)",
      gradientActive: "linear-gradient(135deg, #ff2d95 0%, #ff6eb4 40%, #00d4ff 100%)",
      gradientHero: "linear-gradient(135deg, #fff 0%, #ff6eb4 40%, #00d4ff 80%, #ff2d95 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(255,45,149,0.06) 0%, rgba(0,212,255,0.02) 50%, transparent 100%)",
    },
  },
  {
    id: "cyber-lime",
    name: "Cyber Lime",
    emoji: "\u{26A1}",
    colors: {
      base: "#050a04",
      surface0: "#091208",
      surface1: "#0e1a0c",
      surface2: "#152412",
      surface3: "#1e3018",
      accent: "#84cc16",
      accentBright: "#a3e635",
      accentGhost: "rgba(132,204,22,0.08)",
      accentGlow: "rgba(163,230,53,0.22)",
      gradientActive: "linear-gradient(135deg, #84cc16 0%, #a3e635 50%, #d9f99d 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #a3e635 50%, #84cc16 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(132,204,22,0.05) 0%, transparent 60%)",
    },
  },
  {
    id: "blood-moon",
    name: "Blood Moon",
    emoji: "\u{1F311}",
    colors: {
      base: "#0c0404",
      surface0: "#140808",
      surface1: "#1e0c0c",
      surface2: "#2a1212",
      surface3: "#381818",
      accent: "#dc2626",
      accentBright: "#f87171",
      accentGhost: "rgba(220,38,38,0.10)",
      accentGlow: "rgba(248,113,113,0.22)",
      gradientActive: "linear-gradient(135deg, #dc2626 0%, #f87171 50%, #fca5a5 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #f87171 50%, #dc2626 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(220,38,38,0.05) 0%, transparent 60%)",
    },
  },
  {
    id: "aurora-borealis",
    name: "Aurora",
    emoji: "\u{1F30C}",
    colors: {
      base: "#040a0c",
      surface0: "#081214",
      surface1: "#0c1a1e",
      surface2: "#122428",
      surface3: "#183034",
      accent: "#06b6d4",
      accentBright: "#22d3ee",
      accentGhost: "rgba(6,182,212,0.08)",
      accentGlow: "rgba(34,211,238,0.20)",
      gradientActive: "linear-gradient(135deg, #10b981 0%, #06b6d4 35%, #8b5cf6 70%, #ec4899 100%)",
      gradientHero: "linear-gradient(135deg, #f0f0f8 0%, #22d3ee 30%, #a78bfa 60%, #f472b6 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(6,182,212,0.04) 0%, rgba(139,92,246,0.02) 50%, transparent 100%)",
    },
  },
  {
    id: "molten-core",
    name: "Molten Core",
    emoji: "\u{1F525}",
    colors: {
      base: "#0c0604",
      surface0: "#140c08",
      surface1: "#1e140c",
      surface2: "#2a1c12",
      surface3: "#382618",
      accent: "#ea580c",
      accentBright: "#fb923c",
      accentGhost: "rgba(234,88,12,0.10)",
      accentGlow: "rgba(251,146,60,0.22)",
      gradientActive: "linear-gradient(135deg, #dc2626 0%, #ea580c 35%, #f59e0b 70%, #fbbf24 100%)",
      gradientHero: "linear-gradient(135deg, #fff 0%, #fb923c 40%, #ea580c 70%, #dc2626 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(234,88,12,0.06) 0%, rgba(220,38,38,0.02) 50%, transparent 100%)",
    },
  },
  {
    id: "synthwave",
    name: "Synthwave",
    emoji: "\u{1F3B6}",
    colors: {
      base: "#0c0618",
      surface0: "#120a22",
      surface1: "#1a0f30",
      surface2: "#24163e",
      surface3: "#301e50",
      accent: "#e879f9",
      accentBright: "#f0abfc",
      accentGhost: "rgba(232,121,249,0.08)",
      accentGlow: "rgba(240,171,252,0.22)",
      gradientActive: "linear-gradient(135deg, #6366f1 0%, #e879f9 40%, #f472b6 70%, #fb923c 100%)",
      gradientHero: "linear-gradient(135deg, #fff 0%, #f0abfc 30%, #e879f9 60%, #6366f1 100%)",
      gradientSurface: "linear-gradient(180deg, rgba(232,121,249,0.05) 0%, rgba(99,102,241,0.03) 50%, transparent 100%)",
    },
  },
];

function applyTheme(theme: ThemeDefinition) {
  const root = document.documentElement;
  const c = theme.colors;
  root.style.setProperty("--color-base", c.base);
  root.style.setProperty("--color-surface-0", c.surface0);
  root.style.setProperty("--color-surface-1", c.surface1);
  root.style.setProperty("--color-surface-2", c.surface2);
  root.style.setProperty("--color-surface-3", c.surface3);
  root.style.setProperty("--color-accent", c.accent);
  root.style.setProperty("--color-accent-bright", c.accentBright);
  root.style.setProperty("--color-accent-ghost", c.accentGhost);
  root.style.setProperty("--color-accent-glow", c.accentGlow);
  root.style.setProperty("--gradient-active", c.gradientActive);
  root.style.setProperty("--gradient-hero", c.gradientHero);
  root.style.setProperty("--gradient-surface", c.gradientSurface);
  // Update meta theme-color
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", c.base);
  // Persist
  localStorage.setItem("investmentology-theme", theme.id);
}

interface ThemeStore {
  currentTheme: ThemeDefinition;
  setTheme: (id: string) => void;
}

const savedId = typeof window !== "undefined" ? localStorage.getItem("investmentology-theme") : null;
const initialTheme = themes.find((t) => t.id === savedId) ?? themes[0];

// Apply immediately on load
if (typeof window !== "undefined") {
  applyTheme(initialTheme);
}

export const useThemeStore = create<ThemeStore>((set) => ({
  currentTheme: initialTheme,
  setTheme: (id: string) => {
    const theme = themes.find((t) => t.id === id);
    if (theme) {
      applyTheme(theme);
      set({ currentTheme: theme });
    }
  },
}));
