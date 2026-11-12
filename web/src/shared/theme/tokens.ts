/** Design tokens. Components read these; no colour, size or duration is written anywhere else.
 * Three outcomes carry the whole page, so each owns one colour everywhere: ink blue for a right answer, vermilion for
 * a confidently wrong one, ochre for "not sure". Violet marks a question the agent asked back. Everything else is the
 * grey of a report page, so the outcomes are what the eye finds. */
export const color = {
  surface: "#EEF0F3",
  sheet: "#FFFFFF",
  ink: "#151922",
  muted: "#576071",
  line: "#D2D6DD",
  panel: "#DFE3E9",
  right: "#2352C4",
  rightSoft: "#DCE4F8",
  wrong: "#CC3B26",
  wrongSoft: "#F7DBD5",
  unsure: "#B07F0C",
  unsureSoft: "#F3E7C5",
  ask: "#7446B3",
  focus: "#1D5FD1",
} as const;

export const font = { body: '"Public Sans", system-ui, sans-serif' } as const;

/** A 1.25 scale from 16 px; display is for the page's one sentence. */
export const size = { xs: 12.8, sm: 14, md: 16, lg: 20, xl: 25, xxl: 31.25, display: 42 } as const;
export const weight = { regular: 400, medium: 500, semibold: 600, bold: 700 } as const;
export const leading = { tight: 1.12, snug: 1.3, body: 1.55 } as const;
export const tracking = { display: "-0.015em" } as const;
export const space = [0, 4, 8, 12, 16, 24, 32, 48, 64, 96] as const;
export const radius = { sm: 3, md: 6, lg: 12 } as const;
export const measure = { text: 66, page: 1160 } as const;
export const stroke = { hair: 1, line: 1.5, rule: 2 } as const;
export const motion = {
  fast: 0.16,
  base: 0.3,
  fill: 0.9, // the 100 answers settle into place once, on first load
  cellStagger: 0.006,
  spring: { type: "spring", stiffness: 320, damping: 32 } as const,
  ease: [0.22, 1, 0.36, 1] as [number, number, number, number],
} as const;
export const breakpoint = { narrow: 860 } as const;
export const chart = {
  grid: 10, // 10 x 10 answers per setting
  cell: 18,
  cellGap: 3,
  barHeight: 16,
  labelWidth: 270,
  columns: { num: 92 },
} as const;
