import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { Data, Summary } from "../../shared/data/types";
import { pct, usd } from "../../shared/format";
import { chart, color, font, motion as m, radius, size, space, weight } from "../../shared/theme/tokens";
import { useNarrow } from "../../shared/ui/useNarrow";
import { OUTCOME } from "../answers/Answers";

/** One row per setting: the share of right, wrong and "not sure" answers as one bar, then friction and cost. */
export function Levers({ summary, data, rows }: { summary: Record<string, Summary>; data: Data; rows: string[] }) {
  const narrow = useNarrow();
  const [open, setOpen] = useState<string | null>(null);
  const n = chart.columns.num;
  const cols = narrow ? "1fr" : `${chart.labelWidth}px 1fr ${n}px ${n}px`;
  return (
    <div role="table" aria-label="Lever settings compared">
      {!narrow && (
        <div role="row" style={{ display: "grid", gridTemplateColumns: cols, gap: space[4], fontSize: size.xs, color: color.muted, paddingBottom: space[2] }}>
          <span role="columnheader">Setting</span>
          <span role="columnheader">Answers: right, confidently wrong, not sure</span>
          <span role="columnheader" style={{ textAlign: "right" }}>Asked back per 100</span>
          <span role="columnheader" style={{ textAlign: "right" }}>Cost per right answer</span>
        </div>
      )}
      {rows.map((k) => {
        const s = summary[k];
        const isOpen = open === k;
        return (
          <div key={k} role="rowgroup" style={{ borderTop: `1px solid ${color.line}` }}>
            <button
              type="button"
              role="row"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : k)}
              style={{ display: "grid", gridTemplateColumns: cols, gap: narrow ? space[2] : space[4], alignItems: "center", width: "100%",
                padding: `${space[3]}px 0`, background: "transparent", border: "none", textAlign: "left", cursor: "pointer",
                font: `${weight.regular} ${size.sm}px ${font.body}`, color: color.ink }}
            >
              <span role="cell" style={{ fontWeight: k === "all" ? weight.semibold : weight.regular }}>{data.labels[k]}</span>
              <span role="cell" style={{ display: "flex", height: chart.barHeight, borderRadius: radius.sm, overflow: "hidden" }}>
                {OUTCOME.map((o) => (
                  <span key={o.key} title={`${o.label} ${pct(s[o.key], 1)}`} style={{ width: pct(s[o.key], 2), background: o.fill }} />
                ))}
              </span>
              <span role="cell" style={{ textAlign: narrow ? "left" : "right", color: s.asked_per_100 > 40 ? color.ask : color.ink }}>
                {narrow ? `${Math.round(s.asked_per_100)} questions asked back per 100` : Math.round(s.asked_per_100)}
              </span>
              <span role="cell" style={{ textAlign: narrow ? "left" : "right" }}>{narrow ? `${usd(s.usd_per_correct)} per right answer` : usd(s.usd_per_correct)}</span>
            </button>
            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: m.base, ease: m.ease }}
                  style={{ overflow: "hidden" }}
                >
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: size.sm, margin: `0 0 ${space[4]}px` }}>
                    <caption style={{ textAlign: "left", color: color.muted, fontSize: size.xs, paddingBottom: space[2] }}>
                      {pct(s.correct, 1)} right, {pct(s.wrong, 1)} wrong, {pct(s.missed, 1)} not sure; {s.turns.toFixed(1)} turns, p95 {s.seconds_p95.toFixed(1)} s
                    </caption>
                    <thead>
                      <tr style={{ color: color.muted, textAlign: "left" }}>
                        <th style={{ fontWeight: weight.medium }}>Question kind</th>
                        <th style={{ fontWeight: weight.medium, textAlign: "right" }}>Right</th>
                        <th style={{ fontWeight: weight.medium, textAlign: "right" }}>Wrong</th>
                        <th style={{ fontWeight: weight.medium, textAlign: "right" }}>Not sure</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(data.kinds).map(([kk, label]) => {
                        const d = s.by_kind[kk];
                        if (!d) return null;
                        return (
                          <tr key={kk}>
                            <td>{label} <span style={{ color: color.muted }}>({d.n})</span></td>
                            <td style={{ textAlign: "right" }}>{pct(d.correct ?? 0)}</td>
                            <td style={{ textAlign: "right", color: (d.wrong ?? 0) > 0 ? color.wrong : color.ink }}>{pct(d.wrong ?? 0)}</td>
                            <td style={{ textAlign: "right" }}>{pct(d.missed ?? 0)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
