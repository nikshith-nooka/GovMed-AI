"""Governance Economics — cost rates and risk-adjustment parameters.

These constants drive the stochastic HITL cost model and
risk-adjusted governance overhead calculations used across the pipeline.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Human Review Economics
# ---------------------------------------------------------------------------
# Blended hourly cost for an attending physician's review time, expressed as
# a per-minute rate.  Based on MGMA 2024 median specialist compensation
# (~$350 k / yr) amortised across clinical-contact minutes.
HUMAN_REVIEW_RATE_USD_PER_MIN: float = 14.58

# ---------------------------------------------------------------------------
# Risk-Adjustment Lambda
# ---------------------------------------------------------------------------
# Lambda controls how strongly governance overhead scales with clinical risk.
#   effective_governance_cost = base_cost * (1 + RISK_ADJUSTMENT_LAMBDA * risk_score)
#
# risk_score is normalised to [0, 1].  A lambda of 0 disables risk scaling;
# higher values penalise high-risk cases more aggressively.
RISK_ADJUSTMENT_LAMBDA: float = 0.35

# ---------------------------------------------------------------------------
# Stochastic HITL Distribution Parameters
# ---------------------------------------------------------------------------
# The simulated physician review time is sampled from a normal distribution
# centred on this mean (in minutes).
PHYSICIAN_REVIEW_MINUTES_MEAN: float = 2.5

# Standard deviation of the review-time distribution.
PHYSICIAN_REVIEW_MINUTES_STD: float = 0.8

# Floor / ceiling to keep sampled values physically plausible.
PHYSICIAN_REVIEW_MINUTES_MIN: float = 0.5
PHYSICIAN_REVIEW_MINUTES_MAX: float = 7.0
