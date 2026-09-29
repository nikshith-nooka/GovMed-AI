# Unique contribution (to defend in IEEE review)

## Contribution name
GEF + JRU (Governance Efficiency Frontier + Judge/Rubric Disagreement Uncertainty)

## Why it is unique vs typical governance-cost tradeoff plots
Most governance-cost papers report point estimates such as marginal quality gain per added oversight layer. We go further by (i) constructing a **Pareto frontier** that shows the globally best governance options under cost/quality tradeoffs and (ii) adding **uncertainty calibration** via judge–rubric disagreement, producing **risk-adjusted quality**. This changes the interpretation from “best average” to “best under uncertainty,” which is a stronger, more defensible decision-theoretic claim.

## What we compute (metric definitions)
- **GEF:** A Pareto frontier over variants maximizing **risk-adjusted quality** while minimizing total governance cost.
- **JRU:** Let judge score be `overall_quality_llm_judge` and rubric score be `overall_quality_rubric`. Uncertainty is
  - `uncertainty = |overall_quality_rubric - overall_quality_llm_judge|`
  - `risk_adjusted_quality = overall_quality - λ * uncertainty`
  where `λ` is a configurable risk penalty.

## What we show (figures/tables)
- Figure: **Pareto scatter** of quality vs total governance cost with the frontier highlighted.
- Table: **Frontier composition** and fraction of dominated variants.

## Expected reviewer question & answer
Q: “Is this just another cost curve?”
A: “No. We report the **optimal frontier under uncertainty** (JRU), so ordering can change compared to point-estimate curves. This makes the cost–benefit results decision-relevant and robust.”
