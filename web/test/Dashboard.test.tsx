import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../src/app/App";
import fixture from "./fixture.json";

const ok = () => Promise.resolve(fixture);

describe("dashboard", () => {
  it("shows loading, then 100 answers per setting", async () => {
    render(<App fetcher={ok} />);
    expect(screen.getByRole("status")).toBeTruthy();
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(/four product changes/));
    expect(screen.getAllByRole("img", { name: /right,.*confidently wrong/ })).toHaveLength(2);
  });

  it("explains a failed load and loads again", async () => {
    let calls = 0;
    const flaky = () => (calls++ === 0 ? Promise.reject(new Error("./data.json answered 404")) : Promise.resolve(fixture));
    render(<App fetcher={flaky} />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/404/));
    fireEvent.click(screen.getByRole("button", { name: "Load again" }));
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeTruthy());
  });

  it("says what to run when there are no results", async () => {
    render(<App fetcher={() => Promise.resolve({})} />);
    await waitFor(() => expect(screen.getByText(/No evaluation results yet/)).toBeTruthy());
  });

  it("opens a setting to show errors by kind of question", async () => {
    render(<App fetcher={ok} />);
    const row = (await screen.findAllByRole("row", { name: /All four levers/ }))[0];
    fireEvent.click(row);
    expect(row.getAttribute("aria-expanded")).toBe("true");
    expect((await screen.findAllByText("Question kind")).length).toBeGreaterThan(0);
  });

  it("ranks the levers and shows which are held", async () => {
    render(<App fetcher={ok} />);
    expect((await screen.findAllByText("Held")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("listitem").length).toBeGreaterThan(4);
  });
});
