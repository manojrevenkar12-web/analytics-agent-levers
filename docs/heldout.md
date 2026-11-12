# The held-out company

`config/world_heldout.toml`, run once on the date in `reports/heldout.json`. Same stand-in model, different world:
other data (warehouse seed 101), other accounts, more questions about a single account, a third more questions using
company-defined words, and two phrasings nobody tuned for: "turnover" for revenue and "engaged customers" for active
customers. Neither the metric catalogue nor the stand-in knows them.

What it showed: with all four levers, confidently wrong answers stayed near zero, but one question in five got "not
sure": 30% of questions using company-defined words (the unfamiliar ones among them) against 19% of clear questions. The agent declined rather than guessed, which is the behaviour the
abstain lever exists for, and the catalogue's coverage gap became visible. The product answer is in `docs/brief.md`:
mine "not sure" traces for terms to add.

The lock (`reports/heldout.lock`) fingerprints the parsed settings and the code; a test fails if either changes.
