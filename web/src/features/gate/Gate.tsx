import { motion } from "framer-motion";

import type { Data, GateRow } from "../../shared/data/types";
import { pts } from "../../shared/format";
import { color, motion as m, radius, size, space, weight } from "../../shared/theme/tokens";

/** Each lever against the baseline, and why it ships or is held. */
export function Gate({ gate, data }: { gate: Record<string, GateRow>; data: Data }) {
  const rows = data.order.filter((k) => k !== "baseline");
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: space[2] }}>
      {rows.map((k, i) => {
        const g = gate[k];
        const failed = g.checks.filter((c) => !c.ok).map((c) => c.check);
        return (
          <motion.li key={k} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: m.base, delay: i * m.fast * 0.4 }}
            style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: space[4], padding: `${space[3]}px ${space[4]}px`,
              background: g.ship ? color.sheet : color.panel, borderRadius: radius.md, fontSize: size.sm }}>
            <span>
              <span style={{ fontWeight: weight.semibold }}>{data.labels[k]}</span>
              <span style={{ display: "block", color: color.muted }}>
                {g.ship ? `${pts(g.correct.diff)} right answers, ${pts(g.correct.lo)} at the low end` : `Held: ${failed.join("; ")}`}
              </span>
            </span>
            <span style={{ alignSelf: "center", fontWeight: weight.bold, color: g.ship ? color.right : color.muted }}>{g.ship ? "Ships" : "Held"}</span>
          </motion.li>
        );
      })}
    </ul>
  );
}
