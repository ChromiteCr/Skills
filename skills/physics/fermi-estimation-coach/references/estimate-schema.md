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
- Unknown keys are errors: a misspelt optional key such as `refrence_range` would otherwise switch its check off silently.
- `basis`, `provenance`, units, and the synthesis `decision` must be non-empty strings.
- `low`, `central`, and `high` must be finite positive numbers with `low <= central <= high`.
- `reference_range` is optional. Its unit must equal the mechanism estimate unit.
- `calculation` supports positive `coefficient`, factor IDs in `multiply`, and factor IDs in `divide`. Each listed factor must exist and may occur only once across both lists.
- Every dominant or secondary mechanism must appear in `included_mechanism_ids`. Negligible mechanisms may remain excluded.
- Synthesis `method` is `sum`, `max`, or `product`. The checker recomputes the interval from the included mechanism estimates.
- For `sum` and `max`, every mechanism estimate unit must equal the target unit exactly. For `product`, the included mechanism units are multiplied and the result must equal the target unit: `s^-1` times `J` gives `W`. Write these units as space-separated symbols with integer exponents (`J s^-1`, `W m^-2 K^-1`); `m/s^2`, `W/(m^2 K)` and `s⁻¹` are also read, and everything after `/` is in the denominator. Write `1` for a dimensionless mechanism. SI coherent derived units (`N`, `J`, `W`, `Pa`, `Hz`, `C`, `V`, `F`, `ohm`, `S`, `Wb`, `T`, `H`) are expanded to base units; prefixed and non-SI units (`kW`, `h`, `yr`) stay as their own symbols, so convert them first.
- Target and synthesis estimate units must match exactly. Convert units before creating the worksheet.

The checker uses a default relative arithmetic tolerance of 5%. Override it only for unrounded machine-readable values with `--tolerance`, for example `--tolerance 0.01`.

Exit status: `0` the worksheet passes; `1` validation errors, listed one per line; `2` the file cannot be read or the arguments are wrong. `python3 scripts/check_estimate.py --selftest` runs the regression cases.
