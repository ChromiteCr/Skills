# Using reference values responsibly

Reference values support a plausibility check only when their scope matches the candidate result.

## Required metadata

Record, when available:

- quantity and numerical value;
- unit and conversion applied;
- material, location, temperature, pressure, frequency, epoch, or other conditions that affect it;
- source URL, DOI, standard, textbook edition, or dataset identifier;
- publication date and the date checked;
- uncertainty or stated precision;
- whether it is a measured value, conventional exact value, model output, or rough benchmark.

If provenance or conditions are missing, label the value a **rough benchmark**. Do not present it as authoritative.

## Source preference

Prefer, in order:

1. primary standards and official scientific data services;
2. peer-reviewed primary literature or an identified dataset;
3. reputable handbooks and textbooks with edition information;
4. transparent estimates whose assumptions are shown.

Search snippets, uncited tables, and remembered constants are leads to verify, not evidence.

## Comparison rules

- Convert candidate and reference to the same unit before numeric comparison.
- Match like with like: component versus component, RMS versus peak, local versus global, vacuum versus medium, and measured versus model-defined quantities.
- Compare uncertainty intervals when available.
- Use a range rather than false precision when the quantity varies by context.
- State the ratio and order-of-magnitude gap.
- A mismatch may expose a regime difference rather than an arithmetic error; check conditions before rejecting the result.

## Freshness

Fundamental definitions may be stable, but recommended constants, material properties, records, environmental values, and instrument specifications can change. Recheck mutable values at task time and include the check date. This skill intentionally ships no hard-coded table of supposedly universal reference values.
