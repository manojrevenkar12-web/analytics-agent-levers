import type { Data } from "../../shared/data/types";
import { pts } from "../../shared/format";
import { color, radius, size, space, weight } from "../../shared/theme/tokens";

/** What each lever adds when the other three are on: a ranked sequence, so it is numbered. */
export function ShipOrder({ data }: { data: Data }) {
  const ranked = Object.entries(data.marginal).sort((a, b) => b[1].correct.diff - a[1].correct.diff);
  return (
    <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: space[2] }}>
      {ranked.map(([k, v], i) => (
        <li key={k} style={{ display: "grid", gridTemplateColumns: `${space[6]}px 1fr auto`, gap: space[4], alignItems: "baseline",
          padding: `${space[3]}px ${space[4]}px`, background: color.sheet, borderRadius: radius.md }}>
          <span style={{ fontWeight: weight.bold, fontSize: size.lg, color: color.right }}>{i + 1}</span>
          <span>
            <span style={{ fontWeight: weight.semibold }}>{data.lever_labels[k]}</span>
            <span style={{ display: "block", color: color.muted, fontSize: size.sm }}>
              {pts(v.correct.lo)} to {pts(v.correct.hi)} right answers (95% interval); confidently wrong {pts(v.wrong.diff)}
            </span>
          </span>
          <strong style={{ fontSize: size.lg }}>{pts(v.correct.diff)}</strong>
        </li>
      ))}
    </ol>
  );
}
