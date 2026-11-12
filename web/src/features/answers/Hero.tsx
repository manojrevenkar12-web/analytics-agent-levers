import type { Data } from "../../shared/data/types";
import { pct, usd } from "../../shared/format";
import { color, leading, measure, size, space, tracking, weight } from "../../shared/theme/tokens";
import { useNarrow } from "../../shared/ui/useNarrow";
import { AnswerGrid } from "./Answers";

export function Hero({ data }: { data: Data }) {
  const narrow = useNarrow();
  const b = data.summary.baseline;
  const a = data.summary.all;
  return (
    <header style={{ padding: `${space[8]}px 0 ${space[7]}px` }}>
      <h1 style={{ margin: 0, fontSize: size.display, lineHeight: leading.tight, letterSpacing: tracking.display, fontWeight: weight.bold, maxWidth: "24ch" }}>
        A data agent that is wrong {pct(b.wrong)} of the time, and the four product changes that take it to {pct(a.wrong, 1)}
      </h1>
      <p style={{ margin: `${space[4]}px 0 ${space[7]}px`, maxWidth: `${measure.text}ch`, fontSize: size.lg, lineHeight: leading.body, color: color.muted }}>
        {data.summary.baseline.questions} business questions against a ClickHouse warehouse, asked through the ClickHouse MCP tools. Every
        setting saw the same questions with the same luck. A right answer costs {usd(a.usd_per_correct)} with all four levers, against{" "}
        {usd(b.usd_per_correct)} before.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: narrow ? "1fr" : "1fr 1fr", gap: space[7], maxWidth: measure.page * 0.75 }}>
        <AnswerGrid s={b} title="Schema names only" animate />
        <AnswerGrid s={a} title="With all four levers" animate />
      </div>
    </header>
  );
}
