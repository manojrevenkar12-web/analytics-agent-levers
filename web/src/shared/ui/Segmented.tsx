import { motion } from "framer-motion";

import { color, font, motion as m, radius, size, space, weight } from "../theme/tokens";

/** A small set of mutually exclusive views. The marker slides to the chosen one, so the change is visible. */
export function Segmented<T extends string>({ label, options, value, onChange, id }: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  id: string;
}) {
  return (
    <div role="tablist" aria-label={label} style={{ display: "inline-flex", justifySelf: "start", background: color.panel, borderRadius: radius.md, padding: space[1] }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={on}
            type="button"
            onClick={() => onChange(o.value)}
            style={{
              position: "relative",
              border: "none",
              background: "transparent",
              padding: `${space[2]}px ${space[4]}px`,
              font: `${on ? weight.semibold : weight.medium} ${size.sm}px ${font.body}`,
              color: color.ink,
              cursor: "pointer",
              borderRadius: radius.sm,
            }}
          >
            {on && (
              <motion.span
                layoutId={`seg-${id}`}
                transition={m.spring}
                style={{ position: "absolute", inset: 0, background: color.sheet, borderRadius: radius.sm }}
              />
            )}
            <span style={{ position: "relative" }}>{o.label}</span>
          </button>
        );
      })}
    </div>
  );
}
