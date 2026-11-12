export const int = (x: number) => Math.round(x).toLocaleString("en-GB");
export const pct = (x: number, d = 0) => `${(100 * x).toFixed(d)}%`;
export const pts = (x: number, d = 1) => `${x >= 0 ? "+" : "−"}${Math.abs(100 * x).toFixed(d)} pts`;
export const usd = (x: number, d = 3) => `$${x.toFixed(d)}`;
