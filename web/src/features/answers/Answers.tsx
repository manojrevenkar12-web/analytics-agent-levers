import { motion, useReducedMotion } from "framer-motion";

import type { Summary } from "../../shared/data/types";
import { pct } from "../../shared/format";
import { chart, color, motion as m, size, space, weight } from "../../shared/theme/tokens";

export const OUTCOME = [
  { key: "correct", label: "Right", fill: color.right },
  { key: "wrong", label: "Confidently wrong", fill: color.wrong },
  { key: "missed", label: "Not sure", fill: color.unsure },
] as const;

/** 100 answers, one cell each, in the proportions the setting produced: rights first, then wrongs, then "not sure". */
export function cells(s: Summary): string[] {
  const n = chart.grid * chart.grid;
  const right = Math.round(s.correct * n);
  const wrong = Math.round(s.wrong * n);
  const unsure = Math.max(0, n - right - wrong);
  return [...Array(right).fill(color.right), ...Array(wrong).fill(color.wrong), ...Array(unsure).fill(color.unsure)].slice(0, n);
}

export function AnswerGrid({ s, title, animate }: { s: Summary; title: string; animate: boolean }) {
  const reduce = useReducedMotion();
  const step = chart.cell + chart.cellGap;
  const w = chart.grid * step - chart.cellGap;
  const label = `${title}: ${pct(s.correct)} right, ${pct(s.wrong)} confidently wrong, ${pct(s.missed)} not sure`;
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontWeight: weight.semibold, marginBottom: space[3] }}>{title}</figcaption>
      <svg role="img" aria-label={label} viewBox={`0 0 ${w} ${w}`} style={{ width: "100%", maxWidth: w, display: "block" }}>
        {cells(s).map((fill, i) => (
          <motion.rect
            key={i}
            x={(i % chart.grid) * step}
            y={Math.floor(i / chart.grid) * step}
            width={chart.cell}
            height={chart.cell}
            rx={2}
            fill={fill}
            initial={animate && !reduce ? { opacity: 0 } : false}
            animate={{ opacity: 1 }}
            transition={{ duration: m.base, delay: animate && !reduce ? i * m.cellStagger : 0 }}
          />
        ))}
      </svg>
      <dl style={{ display: "flex", gap: space[5], margin: `${space[3]}px 0 0`, fontSize: size.sm }}>
        {OUTCOME.map((o) => (
          <div key={o.key}>
            <dt style={{ color: color.muted, fontSize: size.xs }}>{o.label}</dt>
            <dd style={{ margin: 0, fontWeight: weight.bold, fontSize: size.xl, color: o.fill }}>{pct(s[o.key])}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
