import type { ReactNode } from "react";

import { color, leading, measure, size, space, weight } from "../theme/tokens";

export function Section({ id, title, lede, children }: { id: string; title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={id} style={{ padding: `${space[7]}px 0`, borderTop: `1px solid ${color.line}` }}>
      <h2 id={id} style={{ margin: 0, fontSize: size.xl, fontWeight: weight.semibold, lineHeight: leading.snug }}>
        {title}
      </h2>
      {lede && (
        <p style={{ margin: `${space[2]}px 0 ${space[5]}px`, maxWidth: `${measure.text}ch`, color: color.muted, lineHeight: leading.body }}>{lede}</p>
      )}
      {children}
    </section>
  );
}
