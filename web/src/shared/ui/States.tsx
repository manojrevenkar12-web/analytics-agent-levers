import { color, font, radius, size, space, weight } from "../theme/tokens";

export const buttonStyle = {
  font: `${weight.semibold} ${size.sm}px ${font.body}`,
  color: color.sheet,
  background: color.right,
  border: "none",
  borderRadius: radius.md,
  padding: `${space[2]}px ${space[4]}px`,
  cursor: "pointer",
} as const;

export function Skeleton() {
  const block = (h: number, w = "100%") => ({ height: h, width: w, borderRadius: radius.md, background: color.panel });
  return (
    <div role="status" aria-busy="true" aria-label="Loading the results" style={{ display: "grid", gap: space[5], padding: `${space[7]}px 0` }}>
      <div style={block(space[7], "70%")} />
      <div style={block(space[9] + space[8])} />
      <div style={block(space[9] + space[8])} />
      <div style={block(space[9] * 2)} />
    </div>
  );
}

export function ErrorNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" style={{ background: color.wrongSoft, borderRadius: radius.md, padding: `${space[4]}px ${space[5]}px`, margin: `${space[7]}px 0` }}>
      <p style={{ margin: 0, fontWeight: weight.semibold }}>The results did not load: {message}.</p>
      <p style={{ margin: `${space[2]}px 0 ${space[4]}px`, color: color.muted }}>
        <code>web/public/data.json</code> is written by <code>python scripts/report.py</code>. Check that it exists, then load it again.
      </p>
      <button type="button" onClick={onRetry} style={buttonStyle}>
        Load again
      </button>
    </div>
  );
}

export function EmptyNotice({ what, command }: { what: string; command: string }) {
  return (
    <p style={{ margin: 0, padding: space[4], borderRadius: radius.md, background: color.panel, color: color.ink }}>
      No {what} yet. Run <code>{command}</code> to produce them.
    </p>
  );
}
