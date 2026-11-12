import type { Data } from "../../shared/data/types";
import { pct } from "../../shared/format";
import { color, leading, measure, radius, space } from "../../shared/theme/tokens";
import { EmptyNotice } from "../../shared/ui/States";
import { Levers } from "../levers/Levers";

export function HeldOut({ data }: { data: Data }) {
  const h = data.heldout;
  if (!h) return <EmptyNotice what="held-out results" command="python scripts/heldout.py --lock && python scripts/heldout.py" />;
  const a = h.summary.all;
  const term = a.by_kind.ambiguous_term;
  const clear = a.by_kind.answerable;
  return (
    <div style={{ display: "grid", gap: space[5] }}>
      <p style={{ margin: 0, maxWidth: `${measure.text}ch`, lineHeight: leading.body, padding: `${space[3]}px ${space[4]}px`, background: color.unsureSoft, borderRadius: radius.md }}>
        With all four levers, confidently wrong answers stayed at {pct(a.wrong, 1)}, but {pct(a.missed)} of questions got "not sure":{" "}
        {pct(term?.missed ?? 0)} of those using company-defined words, which here included "turnover" and "engaged customers", against{" "}
        {pct(clear?.missed ?? 0)} of clear questions. The agent declined instead of guessing; those traces are the data team's list of
        synonyms to add.
      </p>
      <Levers summary={h.summary} data={data} rows={data.order} />
    </div>
  );
}
