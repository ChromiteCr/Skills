# Estimate worksheet schema

The checker accepts one UTF-8 JSON object. All numerical ranges represent positive magnitudes.

```json
{
  "target": {"name": "heat loss", "unit": "W"},
  "mechanisms": [
    {
      "id": "convection",
      "role": "dominant",
      "provenance": "prior mechanism analysis",
      "factors": [
        {
          "id": "h",
          "name": "heat-transfer coefficient",
          "unit": "W m^-2 K^-1",
          "low": 5,
          "central": 10,
          "high": 20,
          "evidence_status": "sourced",
          "basis": "source and access date"
        },
        {
          "id": "area",
          "name": "exposed area",
          "unit": "m^2",
          "low": 1.8,
          "central": 2.0,
          "high": 2.2,
          "evidence_status": "measured",
          "basis": "dimensions supplied by user"
        },
        {
          "id": "delta_t",
          "name": "temperature difference",
          "unit": "K",
          "low": 8,
          "central": 10,
          "high": 12,
          "evidence_status": "measured",
          "basis": "sensor readings"
        }
      ],
      "calculation": {
        "coefficient": 1,
        "multiply": ["h", "area", "delta_t"],
        "divide": []
      },
      "estimate": {"low": 72, "central": 200, "high": 528, "unit": "W"},
      "reference_range": {"low": 50, "high": 1000, "unit": "W"}
    }
  ],
  "synthesis": {
    "method": "sum",
    "included_mechanism_ids": ["convection"],
    "estimate": {"low": 72, "central": 200, "high": 528, "unit": "W"},
    "decision": "Order 10^2 W; measurement needed if the threshold is below 500 W."
  }
}
```

## Required conventions

- Mechanism `role` is one of `dominant`, `secondary`, or `negligible`.
- Factor `evidence_status` is one of `measured`, `sourced`, `derived`, or `assumed`.
- IDs are unique within their scope.
- `basis`, `provenance`, units, and the synthesis `decision` must be non-empty strings.
- `low`, `central`, and `high` must be finite positive numbers with `low <= central <= high`.
- `reference_range` is optional. Its unit must equal the mechanism estimate unit.
- `calculation` supports positive `coefficient`, factor IDs in `multiply`, and factor IDs in `divide`. Each listed factor must exist and may occur only once across both lists.
- Every dominant or secondary mechanism must appear in `included_mechanism_ids`. Negligible mechanisms may remain excluded.
- Synthesis `method` is `sum`, `max`, or `product`. The checker recomputes the interval from the included mechanism estimates.
- Target, mechanism estimate, and synthesis estimate units must match exactly. Convert units before creating the worksheet.

The checker uses a default relative arithmetic tolerance of 5%. Override it only for unrounded machine-readable values with `--tolerance`, for example `--tolerance 0.01`.
