"""Measurement-valid re-analysis of stored benchmark runs.

Everything here is derived from quantities the pipeline actually measured
(stored LLM outputs, token counts, step latencies). Columns that were filled in
after the fact by scripts/backfill_metrics.py (JRU, judge score, HITL minutes)
are audited but never used as evidence.
"""

from __future__ import annotations

import json
import sqlite3
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from scipy import stats

from src.agents.base import is_parse_failure, parse_llm_json
from src.evaluation.scorer import SCORING_FREE_TEXT, ClinicalEvaluationScorer, is_valid_gold_label
from src.evaluation.statistics import (
    cohens_h,
    cohens_kappa_categorical,
    fleiss_kappa,
    holm_bonferroni,
    mcnemar_exact,
    mcnemar_mde,
    mcnemar_power,
    mcnemar_required_n,
    paired_bootstrap,
    rank_biserial,
)

MISDIAGNOSIS_THRESHOLD = 0.5
CORRECT_THRESHOLD = 0.8
ALPHA = 0.05
TARGET_POWER = 0.8
TARGET_DELTA = 0.05
DISCORDANCE_GRID = (0.10, 0.20, 0.30)
REVIEW_CATEGORIES = ("correct", "acceptable", "incorrect")
BACKFILLED_COLUMNS = ("uncertainty_jru", "llm_judge_score", "rubric_quality_score",
                      "risk_adjusted_quality", "governance_efficiency_factor", "hitl_minutes")
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNSPECIFIED"]


def _recover(output: Any) -> Dict[str, Any]:
    if is_parse_failure(output):
        return parse_llm_json(output.get("raw_text", ""))
    return output if isinstance(output, dict) else {}


def _dataset_of(case_id: str) -> str:
    return case_id.split("_")[0] if "_" in case_id else "unknown"


def paired_bootstrap_ci(diffs: np.ndarray, n_boot: int = 5000, seed: int = 7) -> tuple:
    diffs = np.asarray(diffs, dtype=float)
    if len(diffs) == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    means = rng.choice(diffs, size=(n_boot, len(diffs)), replace=True).mean(axis=1)
    return float(diffs.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def wilcoxon_p(diffs: np.ndarray) -> float:
    diffs = np.asarray(diffs, dtype=float)
    if len(diffs) < 5 or np.allclose(diffs, 0):
        return 1.0
    return float(stats.wilcoxon(diffs, zero_method="wilcox").pvalue)


def auroc(scores: np.ndarray, labels: np.ndarray) -> Optional[float]:
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return None
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return float(u / (len(pos) * len(neg)))


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    if len(a) == 0:
        return None
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return None if pe == 1 else (po - pe) / (1 - pe)


def expected_calibration_error(prob: np.ndarray, correct: np.ndarray, n_bins: int = 10) -> Dict[str, Any]:
    prob, correct = np.asarray(prob, float), np.asarray(correct, float)
    edges = np.linspace(0, 1, n_bins + 1)
    bins, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob < hi if hi < 1 else prob <= hi)
        if not mask.any():
            continue
        conf, acc = float(prob[mask].mean()), float(correct[mask].mean())
        ece += mask.mean() * abs(conf - acc)
        bins.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": int(mask.sum()), "mean_confidence": round(conf, 3),
                     "observed_accuracy": round(acc, 3)})
    if not len(prob):
        return {"ece": None, "brier": None, "n": 0, "bins": []}
    brier = float(np.mean((prob - correct) ** 2))
    return {"ece": round(float(ece), 4), "brier": round(brier, 4), "n": int(len(prob)), "bins": bins}


def _r(x: Any, nd: int = 4) -> Any:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def load_cases(cases_path: Union[str, Sequence[str]]) -> Dict[str, Dict[str, Any]]:
    """Case lookup by id from one or more benchmark files (list, or comma-separated string).

    With several paths, missing files are skipped so a default can name optional benchmarks.
    """
    paths = [p.strip() for p in cases_path.split(",")] if isinstance(cases_path, str) else list(cases_path)
    paths = [p for p in paths if p]
    existing = [p for p in paths if Path(p).exists()] if len(paths) > 1 else paths
    if not existing:
        raise FileNotFoundError(f"No benchmark case file found among {paths}")
    cases: Dict[str, Dict[str, Any]] = {}
    for p in existing:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        for c in (data["cases"] if isinstance(data, dict) else data):
            cases[c.get("id") or c["case_id"]] = c
    return cases


def has_answer_key(case: Dict[str, Any]) -> bool:
    options = case.get("options") or {}
    key = str(case.get("answer_idx") or case.get("answer") or "").strip().upper()
    return bool(options) and key in {str(k).upper() for k in options}


def is_measured_jru(jru_source: Any, judge_model: Any, generator_model: Any) -> bool:
    """JRU is a measurement only when an independent (different-model) judge produced it."""
    judge = str(judge_model or "").strip().lower()
    return (str(jru_source or "") == "judge_rubric" and bool(judge)
            and judge != str(generator_model or "").strip().lower())


def _power_block(n: int, discordance: float) -> Dict[str, Any]:
    mde = mcnemar_mde(n, discordance, ALPHA, TARGET_POWER) if discordance > 0 else None
    return {
        "n_pairs": int(n), "discordance_rate": _r(discordance, 4),
        "min_detectable_accuracy_diff": _r(mde, 4),
        # A difference larger than the discordance rate is impossible, so its power is undefined.
        "power_for_5pt_diff": _r(mcnemar_power(n, TARGET_DELTA, discordance, ALPHA), 3)
        if discordance >= TARGET_DELTA else None,
        "required_n_for_5pt_diff": mcnemar_required_n(TARGET_DELTA, discordance, ALPHA, TARGET_POWER),
    }


class RigorousAnalysis:
    """Re-scores stored runs from raw outputs and produces a publication-grade evidence report."""

    def __init__(self, db_path: str = "results/benchmark_results.db",
                 cases_path: Union[str, Sequence[str]] = "benchmarks/curated_sample.json",
                 reference_db_path: Optional[str] = "results/benchmark_results.db.bak"):
        self.db_path = db_path
        self.reference_db_path = reference_db_path
        self.cases = load_cases(cases_path)
        self.scorer = ClinicalEvaluationScorer()
        with sqlite3.connect(db_path) as conn:
            self.raw_runs = pd.read_sql_query("SELECT * FROM runs", conn)
            self.steps = pd.read_sql_query("SELECT run_id, variant_id, agent_name, latency_ms, total_tokens FROM agent_steps", conn)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.reviews = (pd.read_sql_query("SELECT * FROM clinician_reviews", conn)
                            if "clinician_reviews" in tables else pd.DataFrame())
        # Older run databases predate some columns; treat them as unmeasured rather than failing.
        for col in BACKFILLED_COLUMNS:
            if col not in self.raw_runs.columns:
                self.raw_runs[col] = np.nan
        self.runs = self._rescore()

    # ------------------------------------------------------------------ rescoring
    def _rescore_row(self, row: pd.Series) -> Dict[str, Any]:
        raw = json.loads(row["raw_outputs_json"] or "{}")
        case = self.cases.get(row["case_id"], {})
        parse_failed = [k for k, v in raw.items() if is_parse_failure(v)]
        diagnosis = _recover(raw.get("diagnosis", {}))
        verifier = _recover(raw.get("verifier")) if "verifier" in raw else None
        safety = _recover(raw.get("safety")) if "safety" in raw else None
        hitl = _recover(raw.get("hitl")) if "hitl" in raw else None

        primary = str(diagnosis.get("primary_diagnosis", "") or "")
        diffs = diagnosis.get("differential_diagnoses", []) or []
        diffs = [d for d in diffs if isinstance(d, dict)]
        gold = case.get("gold_diagnosis", "")
        scored = self.scorer.score_diagnosis(primary, diffs, case)
        acc = scored["score"]
        comp = self.scorer.evaluate_completeness(diffs)
        w = self.scorer.rubrics

        prob = None
        for d in diffs:
            if d.get("rank") == 1 and isinstance(d.get("probability"), (int, float)):
                prob = float(d["probability"])
        if prob is None and diffs and isinstance(diffs[0].get("probability"), (int, float)):
            prob = float(diffs[0]["probability"])
        if prob is not None and prob > 1:
            prob = prob / 100.0

        flags = [f for f in (safety or {}).get("safety_flags", []) or [] if isinstance(f, dict)]
        severities = [str(f.get("severity", "UNSPECIFIED")).upper() or "UNSPECIFIED" for f in flags]
        return {
            "run_id": row["id"],
            "case_id": row["case_id"],
            "variant_id": row["variant_id"],
            "dataset": _dataset_of(row["case_id"]),
            "specialty": case.get("specialty", "Unknown"),
            "difficulty": case.get("difficulty", "Unknown"),
            "gold_valid": is_valid_gold_label(gold) or has_answer_key(case),
            "scoring_mode": scored["scoring_mode"],
            "option_parse_status": scored["parse_status"],
            "option_unparsed": bool(scored["flagged"]),
            "correct": bool(acc >= CORRECT_THRESHOLD),
            "model": row.get("model"),
            "jru_source": row.get("jru_source"),
            "judge_model": row.get("judge_model"),
            "uncertainty_jru": row.get("uncertainty_jru"),
            "primary_diagnosis": primary,
            "primary_norm": " ".join(primary.lower().split()),
            "diagnosis_parse_failed": "diagnosis" in parse_failed,
            "parse_failed_agents": parse_failed,
            "reported_accuracy": float(row["diagnostic_accuracy_score"] or 0),
            "accuracy": acc,
            "completeness": comp,
            "detector_neutral_quality": (acc * w["diagnostic_weight"] + comp * w["completeness_weight"])
            / (w["diagnostic_weight"] + w["completeness_weight"]),
            "reported_quality": float(row["overall_quality_score"] or 0),
            "model_probability": prob,
            "hallucination_flag": bool((verifier or {}).get("hallucination_detected")) if verifier is not None else None,
            "safety_alerts": len(flags) if safety is not None else None,
            "safety_alerts_high": sum(s in ("HIGH", "CRITICAL") for s in severities) if safety is not None else None,
            "severities": severities,
            "hitl_decision": str((hitl or {}).get("decision", "")).upper() if hitl is not None else None,
            "tokens": float(row["total_tokens"] or 0),
            "cost_usd": float(row["total_cost_usd"] or 0),
            "reported_latency_s": float(row["total_latency_ms"] or 0) / 1000.0,
        }

    def _rescore(self) -> pd.DataFrame:
        df = pd.DataFrame([self._rescore_row(r) for _, r in self.raw_runs.iterrows()])
        # Keep one run per (case, variant): the latest, matching how checkpointing resumes.
        df = df.sort_values("run_id").drop_duplicates(["case_id", "variant_id"], keep="last")
        e2e = self.steps.groupby("run_id")["latency_ms"].sum() / 1000.0
        df["e2e_latency_s"] = df["run_id"].map(e2e).fillna(df["reported_latency_s"])
        return df.reset_index(drop=True)

    # ------------------------------------------------------------------ sections
    def integrity_audit(self) -> Dict[str, Any]:
        notes: List[str] = []
        synthetic: List[str] = []
        ref = self.reference_db_path
        if ref and Path(ref).exists():
            with sqlite3.connect(ref) as conn:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(runs)")}
                for col in BACKFILLED_COLUMNS:
                    ref_filled = (conn.execute(f"SELECT COUNT({col}) FROM runs").fetchone()[0] if col in cols else 0)
                    now_filled = int(self.raw_runs[col].notna().sum()) if col in self.raw_runs else 0
                    if ref_filled == 0 and now_filled > 0:
                        synthetic.append(col)
            if synthetic:
                notes.append(f"Columns empty in the original run database but populated now: {', '.join(synthetic)}. "
                             "They were produced by a post-hoc script, not measured, and are excluded from all evidence.")
        judge_derived = False
        r = self.raw_runs.dropna(subset=["llm_judge_score", "overall_quality_score", "uncertainty_jru"])
        if len(r):
            resid = (r["llm_judge_score"] - (r["overall_quality_score"] - 0.05 * r["uncertainty_jru"]).clip(0, 1)).abs()
            judge_derived = bool((resid < 1e-3).mean() > 0.95)
            if judge_derived:
                notes.append("llm_judge_score equals overall_quality - 0.05*JRU in >95% of rows: it is derived "
                             "from the rubric, so no independent LLM judge scored these runs.")
        jru = self.raw_runs.groupby("variant_id")["uncertainty_jru"].agg(["min", "max"])
        floors = {v: _r(x) for v, x in jru["min"].items()}
        return {"synthetic_columns": synthetic, "judge_score_is_derived": judge_derived,
                "jru_min_by_variant": floors, "notes": notes}

    def measurement_validity(self) -> Dict[str, Any]:
        df = self.runs
        agent_fail: Dict[str, Dict[str, int]] = {}
        for agents in df["parse_failed_agents"]:
            for a in agents:
                agent_fail.setdefault(a, {"failed": 0})["failed"] += 1
        totals: Dict[str, int] = {}
        kept = set(df["run_id"])
        for _, row in self.raw_runs[self.raw_runs["id"].isin(kept)].iterrows():
            for k in json.loads(row["raw_outputs_json"] or "{}"):
                totals[k] = totals.get(k, 0) + 1
        return {
            "parse_failure_rate_by_agent": {k: {"failed": v["failed"], "total": totals.get(k, 0),
                                                "rate": _r(v["failed"] / max(1, totals.get(k, 0)), 3)}
                                            for k, v in agent_fail.items()},
            "runs_with_unparsed_diagnosis": int(df["diagnosis_parse_failed"].sum()),
            "runs_with_option_letter_diagnosis": int(df["primary_norm"].str.fullmatch(r"[a-e]").sum()),
            "reported_accuracy_on_option_letter_runs": _r(
                df.loc[df["primary_norm"].str.fullmatch(r"[a-e]"), "reported_accuracy"].mean(), 3),
            "reported_accuracy_on_unparsed_runs": _r(df.loc[df["diagnosis_parse_failed"], "reported_accuracy"].mean(), 3),
            "reported_accuracy_mean": _r(df["reported_accuracy"].mean(), 3),
            "corrected_accuracy_mean_all_cases": _r(df["accuracy"].mean(), 3),
            "corrected_accuracy_mean_valid_gold": _r(df.loc[df["gold_valid"], "accuracy"].mean(), 3),
            "reported_accuracy_mean_valid_gold": _r(df.loc[df["gold_valid"], "reported_accuracy"].mean(), 3),
            "cases_total": int(df["case_id"].nunique()),
            "cases_with_valid_gold": int(df.loc[df["gold_valid"], "case_id"].nunique()),
            "templated_gold_by_dataset": df.loc[~df["gold_valid"]].groupby("dataset")["case_id"].nunique().to_dict(),
            "cases_with_answer_key": int(df.loc[df["scoring_mode"] != SCORING_FREE_TEXT, "case_id"].nunique()),
            "runs_by_scoring_mode": df["scoring_mode"].value_counts().to_dict(),
            "option_parse_status_counts": df.loc[df["scoring_mode"] != SCORING_FREE_TEXT, "option_parse_status"]
            .value_counts().to_dict(),
            "runs_with_unparseable_option_answer": int(df["option_unparsed"].sum()),
            "latency_note": "Reported total_latency_ms excludes the shared Research and Diagnosis steps; "
                            "e2e_latency sums every agent step.",
        }

    def variant_summary(self) -> List[Dict[str, Any]]:
        df, out = self.runs, []
        base = df[df["variant_id"] == "V1"].set_index("case_id")["primary_norm"]
        for vid, g in df.groupby("variant_id"):
            valid = g[g["gold_valid"]]
            changed = g.set_index("case_id")["primary_norm"].reindex(base.index)
            out.append({
                "variant_id": vid,
                "n_runs": int(len(g)),
                "accuracy_valid_gold": _r(valid["accuracy"].mean()),
                "detector_neutral_quality": _r(g["detector_neutral_quality"].mean()),
                "reported_quality": _r(g["reported_quality"].mean()),
                "tokens_mean": _r(g["tokens"].mean(), 1),
                "cost_mean_usd": _r(g["cost_usd"].mean(), 6),
                "safety_alerts_total": int(g["safety_alerts"].fillna(0).sum()),
                "hallucination_flags_total": int(g["hallucination_flag"].fillna(False).astype(bool).sum()),
                "e2e_latency_p50_s": _r(g["e2e_latency_s"].median(), 1),
                "e2e_latency_p95_s": _r(g["e2e_latency_s"].quantile(0.95), 1),
                "hallucination_flag_rate": _r(g["hallucination_flag"].dropna().astype(float).mean()) if g["hallucination_flag"].notna().any() else None,
                "safety_alerts_per_run": _r(g["safety_alerts"].dropna().mean()) if g["safety_alerts"].notna().any() else None,
                "diagnosis_changed_vs_v1_pct": _r(100 * float((changed != base).mean()), 1) if vid != "V1" else 0.0,
            })
        return out

    def paired_tests(self) -> List[Dict[str, Any]]:
        df, out = self.runs, []
        for metric, subset in (("accuracy", "gold_valid"), ("detector_neutral_quality", None),
                               ("reported_quality", None), ("tokens", None), ("e2e_latency_s", None)):
            data = df[df[subset]] if subset else df
            wide = data.pivot_table(index="case_id", columns="variant_id", values=metric)
            for vid in [c for c in wide.columns if c != "V1"]:
                pair = wide[["V1", vid]].dropna()
                diffs = (pair[vid] - pair["V1"]).to_numpy()
                mean, lo, hi = paired_bootstrap_ci(diffs)
                rb, rb_lo, rb_hi = paired_bootstrap(pair["V1"].to_numpy(), pair[vid].to_numpy(),
                                                    lambda a, b: rank_biserial(b - a), n_boot=1000)
                out.append({"metric": metric, "comparison": f"{vid} - V1", "n_pairs": int(len(pair)),
                            "mean_diff": _r(mean), "ci95_low": _r(lo), "ci95_high": _r(hi),
                            "wilcoxon_p": _r(wilcoxon_p(diffs), 6),
                            "rank_biserial": _r(rb, 3), "rank_biserial_ci95_low": _r(rb_lo, 3),
                            "rank_biserial_ci95_high": _r(rb_hi, 3)})
        return out

    def _paired_correct(self) -> Dict[str, pd.DataFrame]:
        """Per comparison: V1 and variant binary correctness on the same scorable cases."""
        df = self.runs[self.runs["gold_valid"]]
        wide = df.pivot_table(index="case_id", columns="variant_id", values="correct", aggfunc="max")
        if "V1" not in wide.columns:
            return {}
        return {vid: wide[["V1", vid]].dropna().astype(bool) for vid in wide.columns if vid != "V1"}

    def accuracy_tests(self) -> List[Dict[str, Any]]:
        """Exact McNemar on paired binary correctness vs V1, with accuracy-difference and Cohen's h CIs."""
        out = []
        for vid, pair in self._paired_correct().items():
            a, b = pair["V1"].to_numpy(), pair[vid].to_numpy()
            test = mcnemar_exact(a, b)
            diff, d_lo, d_hi = paired_bootstrap(a, b, lambda x, y: float(y.mean() - x.mean()))
            h, h_lo, h_hi = paired_bootstrap(a, b, lambda x, y: cohens_h(float(x.mean()), float(y.mean())))
            out.append({"comparison": f"{vid} - V1", "n_pairs": test["n_pairs"],
                        "accuracy_v1": _r(a.mean()), "accuracy_variant": _r(b.mean()),
                        "only_v1_correct": test["only_a_correct"], "only_variant_correct": test["only_b_correct"],
                        "discordance_rate": _r(test["n_discordant"] / max(1, test["n_pairs"])),
                        "accuracy_diff": _r(diff), "accuracy_diff_ci95_low": _r(d_lo), "accuracy_diff_ci95_high": _r(d_hi),
                        "cohens_h": _r(h, 3), "cohens_h_ci95_low": _r(h_lo, 3), "cohens_h_ci95_high": _r(h_hi, 3),
                        "mcnemar_exact_p": _r(test["p_value"], 6)})
        return out

    def closed_loop_effect(self) -> List[Dict[str, Any]]:
        """Closed vs open loop on the same cases (X-CL vs X): exact McNemar, Holm across X, and revision outcomes."""
        df = self.runs[self.runs["gold_valid"]]
        wide = df.pivot_table(index="case_id", columns="variant_id", values="correct", aggfunc="max")
        revised = self.raw_runs.set_index("variant_id")["revision_applied"] if "revision_applied" in self.raw_runs else None
        out = []
        for cl in [c for c in wide.columns if str(c).endswith("-CL") and str(c)[:-3] in wide.columns]:
            base = str(cl)[:-3]
            pair = wide[[base, cl]].dropna().astype(bool)
            a, b = pair[base].to_numpy(), pair[cl].to_numpy()
            test = mcnemar_exact(a, b)
            diff, lo, hi = paired_bootstrap(a, b, lambda x, y: float(y.mean() - x.mean()))
            rev = revised.loc[[cl]] if revised is not None and cl in revised.index else pd.Series(dtype=float)
            out.append({"comparison": f"{cl} - {base}", "n_pairs": test["n_pairs"],
                        "accuracy_open": _r(a.mean()), "accuracy_closed": _r(b.mean()),
                        "fixed_by_revision": test["only_b_correct"], "broken_by_revision": test["only_a_correct"],
                        "revision_rate": _r(rev.fillna(0).astype(float).mean()) if len(rev) else None,
                        "accuracy_diff": _r(diff), "accuracy_diff_ci95_low": _r(lo), "accuracy_diff_ci95_high": _r(hi),
                        "mcnemar_exact_p": _r(test["p_value"], 6)})
        for row, adj in zip(out, holm_bonferroni([r["mcnemar_exact_p"] for r in out]), strict=True):
            row["mcnemar_exact_p_holm"] = _r(adj, 6)
        return out

    @staticmethod
    def apply_holm(paired: List[Dict[str, Any]], acc_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Holm-Bonferroni over every paired comparison in the report (Wilcoxon rows + McNemar rows)."""
        family = [(row, "wilcoxon_p") for row in paired] + [(row, "mcnemar_exact_p") for row in acc_tests]
        adjusted = holm_bonferroni([row.get(key) for row, key in family])
        for (row, key), adj in zip(family, adjusted, strict=True):
            row[f"{key}_holm"] = _r(adj, 6)
        n_sig_raw = sum(1 for row, key in family if row.get(key) is not None and row[key] < ALPHA)
        n_sig_adj = sum(1 for adj in adjusted if adj is not None and adj < ALPHA)
        return {"method": "holm-bonferroni", "alpha": ALPHA, "family_size": sum(a is not None for a in adjusted),
                "family": "all paired Wilcoxon tests (every metric x variant vs V1) and exact McNemar accuracy tests",
                "significant_raw": n_sig_raw, "significant_after_holm": n_sig_adj}

    def power_analysis(self, acc_tests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Paired-McNemar power (Connor, 1987) at alpha 0.05 / power 0.8 for the observed n and discordance."""
        per = []
        for t in acc_tests:
            block = _power_block(t["n_pairs"], t["discordance_rate"] or 0.0)
            per.append({"comparison": t["comparison"], **block})
        pairs = self._paired_correct()
        n_obs = int(max((len(p) for p in pairs.values()), default=0))
        disc = [t["discordance_rate"] for t in acc_tests if t["discordance_rate"]]
        pooled = float(np.mean(disc)) if disc else 0.0
        return {
            "method": "Connor (1987) normal approximation for the paired McNemar test",
            "alpha": ALPHA, "target_power": TARGET_POWER, "target_accuracy_diff": TARGET_DELTA,
            "per_comparison": per,
            "pooled": _power_block(n_obs, pooled) if n_obs else None,
            "min_detectable_diff_at_observed_n_by_assumed_discordance": {
                f"{psi:.2f}": _r(mcnemar_mde(n_obs, psi, ALPHA, TARGET_POWER), 4) for psi in DISCORDANCE_GRID} if n_obs else {},
            "required_n_for_5pt_diff_by_assumed_discordance": {
                f"{psi:.2f}": mcnemar_required_n(TARGET_DELTA, psi, ALPHA, TARGET_POWER) for psi in DISCORDANCE_GRID},
            "note": ("Discordance = share of cases where exactly one of V1 / variant is correct. With zero observed "
                     "discordance the test cannot reject; the assumed-discordance grid gives planning sample sizes."),
        }

    def jru_measurement(self) -> Dict[str, Any]:
        """JRU counts as measured only when a different-model judge produced it (jru_source == judge_rubric)."""
        df = self.runs
        measured = df.apply(lambda r: is_measured_jru(r["jru_source"], r["judge_model"], r["model"]), axis=1) \
            if len(df) else pd.Series(dtype=bool)
        sources = df["jru_source"].fillna("unrecorded").value_counts().to_dict()
        by_variant = {vid: _r(g.loc[measured[g.index], "uncertainty_jru"].astype(float).mean())
                      for vid, g in df.groupby("variant_id") if measured[g.index].any()}
        n = int(measured.sum()) if len(measured) else 0
        return {"n_runs_measured": n, "jru_source_counts": sources,
                "judge_models": sorted({str(m) for m in df.loc[measured, "judge_model"].dropna()}) if n else [],
                "mean_jru_by_variant": by_variant,
                "status": "measured" if n else
                "not measured: no run was scored by a judge model different from the generator"}

    def audit_paradox(self) -> List[Dict[str, Any]]:
        df, out = self.runs, []
        base = df[df["variant_id"] == "V1"]
        for vid, g in df.groupby("variant_id"):
            if vid == "V1":
                continue
            q_drop = base["reported_quality"].mean() - g["reported_quality"].mean()
            n_drop = base["detector_neutral_quality"].mean() - g["detector_neutral_quality"].mean()
            out.append({"variant_id": vid, "reported_quality_drop": _r(q_drop),
                        "detector_neutral_quality_drop": _r(n_drop),
                        "share_of_drop_from_detector_penalties": _r(1 - n_drop / q_drop, 3) if abs(q_drop) > 1e-6 else None})
        return out

    def alert_discrimination(self) -> List[Dict[str, Any]]:
        """Do governance signals fire more on wrong diagnoses than on right ones?"""
        df = self.runs[self.runs["gold_valid"]]
        signals = [("hallucination_flag", lambda s: s.astype(float)), ("safety_alerts", lambda s: s.astype(float)),
                   ("safety_alerts_high", lambda s: s.astype(float)),
                   ("hitl_decision", lambda s: s.isin(["REQUEST_REVISION", "REJECTED"]).astype(float))]
        out = []
        for col, to_score in signals:
            for vid, g in df[df[col].notna()].groupby("variant_id"):
                score = to_score(g[col]).to_numpy()
                wrong = (g["accuracy"] < MISDIAGNOSIS_THRESHOLD).to_numpy()
                fired = score > 0
                tp, fp = int((fired & wrong).sum()), int((fired & ~wrong).sum())
                out.append({"signal": col, "variant_id": vid, "n": int(len(g)),
                            "misdiagnosis_prevalence": _r(wrong.mean(), 3),
                            "fire_rate": _r(fired.mean(), 3),
                            "sensitivity": _r(tp / max(1, wrong.sum()), 3),
                            "false_positive_rate": _r(fp / max(1, (~wrong).sum()), 3),
                            "precision": _r(tp / max(1, fired.sum()), 3) if fired.any() else None,
                            "auroc": _r(auroc(score, wrong), 3)})
        return out

    def alert_reproducibility(self) -> Dict[str, Any]:
        """V4 and V5 run the same safety validator on the same cached diagnosis; alerts should agree."""
        df = self.runs.dropna(subset=["safety_alerts"])
        wide = df.pivot_table(index="case_id", columns="variant_id", values="safety_alerts")
        if not {"V4", "V5"} <= set(wide.columns):
            return {}
        pair = wide[["V4", "V5"]].dropna()
        rho = stats.spearmanr(pair["V4"], pair["V5"]).statistic if len(pair) > 2 else None
        exact = float((pair["V4"] == pair["V5"]).mean())
        sev = pd.Series([s for lst in df["severities"] for s in lst]).value_counts().to_dict()
        return {"n_cases": int(len(pair)), "any_alert_kappa": _r(cohen_kappa(pair["V4"] > 0, pair["V5"] > 0), 3),
                "alert_count_spearman": _r(rho, 3), "identical_alert_count_pct": _r(100 * exact, 1),
                "severity_distribution": {k: int(sev.get(k, 0)) for k in SEVERITY_ORDER if sev.get(k)}}

    def hitl_analysis(self) -> List[Dict[str, Any]]:
        df = self.runs[self.runs["gold_valid"] & self.runs["hitl_decision"].notna()]
        out = []
        for (vid, dec), g in df.groupby(["variant_id", "hitl_decision"]):
            out.append({"variant_id": vid, "decision": dec, "n": int(len(g)),
                        "misdiagnosis_rate": _r((g["accuracy"] < MISDIAGNOSIS_THRESHOLD).mean(), 3)})
        return out

    def calibration(self) -> Dict[str, Any]:
        df = self.runs[(self.runs["variant_id"] == "V1") & self.runs["gold_valid"] & self.runs["model_probability"].notna()]
        return expected_calibration_error(df["model_probability"].clip(0, 1).to_numpy(),
                                          (df["accuracy"] >= CORRECT_THRESHOLD).to_numpy())

    def latency_by_agent(self) -> List[Dict[str, Any]]:
        s = self.steps[self.steps["run_id"].isin(set(self.runs["run_id"]))].copy()
        s["agent"] = s["agent_name"].str.replace(r" \(Revision\)", "", regex=True)
        total = s.groupby("run_id")["latency_ms"].sum()
        s["share"] = s["latency_ms"] / s["run_id"].map(total)
        out = [{"agent": a, "calls": int(len(x)), "mean_s": _r(x["latency_ms"].mean() / 1000, 1),
                "p95_s": _r(x["latency_ms"].quantile(0.95) / 1000, 1), "max_s": _r(x["latency_ms"].max() / 1000, 1),
                "mean_share_of_run": _r(x["share"].mean(), 3), "mean_tokens": _r(x["total_tokens"].mean(), 0)}
               for a, x in s.groupby("agent")]
        return sorted(out, key=lambda r: -(r["mean_s"] or 0))

    def strata(self) -> Dict[str, List[Dict[str, Any]]]:
        df = self.runs[(self.runs["variant_id"] == "V1")]
        out = {}
        for key in ("dataset", "specialty", "difficulty"):
            rows = []
            for val, g in df.groupby(key):
                valid = g[g["gold_valid"]]
                rows.append({key: val, "cases": int(len(g)), "cases_valid_gold": int(len(valid)),
                             "accuracy_valid_gold": _r(valid["accuracy"].mean(), 3) if len(valid) else None,
                             "diagnosis_parse_failure_rate": _r(g["diagnosis_parse_failed"].mean(), 3)})
            out[key] = sorted(rows, key=lambda r: -r["cases"])
        return out

    def failure_taxonomy(self) -> Dict[str, Any]:
        df = self.runs[self.runs["gold_valid"]]
        v1 = df[df["variant_id"] == "V1"].set_index("case_id")
        wrong = v1[v1["accuracy"] < MISDIAGNOSIS_THRESHOLD].index
        caught = {"verifier": 0, "safety_high": 0, "hitl": 0}
        missed_all = 0
        for _, g in df[df["case_id"].isin(wrong)].groupby("case_id"):
            v = bool(g["hallucination_flag"].fillna(False).astype(bool).any())
            s = bool((g["safety_alerts_high"].fillna(0) > 0).any())
            h = bool(g["hitl_decision"].isin(["REQUEST_REVISION", "REJECTED"]).any())
            caught["verifier"] += v
            caught["safety_high"] += s
            caught["hitl"] += h
            missed_all += not (v or s or h)
        confident_wrong = v1.loc[wrong]["model_probability"].dropna()
        examples = [{"case_id": cid, "gold": self.cases[cid]["gold_diagnosis"], "predicted": v1.loc[cid, "primary_diagnosis"]}
                    for cid in list(wrong)[:8]]
        return {"misdiagnosed_cases_v1": int(len(wrong)), "flagged_by_any_variant": caught,
                "missed_by_all_governance": int(missed_all),
                "confident_wrong_ge_0_7": int((confident_wrong >= 0.7).sum()), "examples": examples}

    def clinician_validation(self) -> Dict[str, Any]:
        """Inter-rater agreement (Fleiss for >= 3 raters per item, Cohen for 2) and clinician vs scorer."""
        empty = {"n_reviews": 0, "n_reviewers": 0, "n_items": 0, "alert_precision_by_clinicians": None,
                 "n_alerts_rated": 0, "auto_vs_clinician_agreement": None, "auto_vs_clinician_kappa": None,
                 "inter_rater": {"status": "insufficient_data", "method": None, "kappa": None},
                 "status": "insufficient_data: no clinician reviews yet. Collect them in the Clinician Review "
                           "page using the fixed set in benchmarks/clinician_protocol_50.json."}
        if self.reviews.empty:
            return empty
        rv = self.reviews.merge(self.runs[["run_id", "accuracy", "variant_id"]], on="run_id", how="left")
        alert_labels = [a for lst in rv["alert_ratings"].map(lambda s: json.loads(s or "[]")) for a in lst]
        valid = [a for a in alert_labels if a.get("verdict") in ("valid", "invalid")]
        rated = rv[rv["diagnosis_verdict"].isin(REVIEW_CATEGORIES)]

        # Clinician consensus per item (majority; ties dropped) against the automatic scorer.
        agreement: Dict[str, Any] = {}
        consensus = []
        for _, g in rated.groupby("run_id"):
            counts = g["diagnosis_verdict"].value_counts()
            if len(counts) > 1 and counts.iloc[0] == counts.iloc[1]:
                continue
            acc = g["accuracy"].iloc[0]
            if acc == acc:  # not NaN: the run is still in the analysed set
                consensus.append((counts.index[0], bool(acc >= CORRECT_THRESHOLD)))
        for label, positives in (("strict", {"correct"}), ("lenient", {"correct", "acceptable"})):
            human = np.array([v in positives for v, _ in consensus], bool)
            auto = np.array([a for _, a in consensus], bool)
            agreement[label] = {"n_items": len(consensus),
                                "agreement": _r((human == auto).mean(), 3) if consensus else None,
                                "kappa": _r(cohen_kappa(auto, human), 3) if consensus else None}

        inter = self._inter_rater(rated)
        n_items = int(rated["run_id"].nunique())
        status = ("ok" if inter["status"] == "ok" and consensus else
                  "insufficient_data: " + "; ".join(r for r in (
                      None if consensus else "no scorable consensus verdicts",
                      None if inter["status"] == "ok" else inter["status"]) if r))
        return {"n_reviews": int(len(rv)), "n_reviewers": int(rv["reviewer_id"].nunique()), "n_items": n_items,
                "verdict_counts": rv["diagnosis_verdict"].value_counts().to_dict(),
                "alert_precision_by_clinicians": _r(sum(a["verdict"] == "valid" for a in valid) / len(valid), 3) if valid else None,
                "n_alerts_rated": len(valid),
                "auto_vs_clinician_agreement": agreement["strict"]["agreement"],
                "auto_vs_clinician_kappa": agreement["strict"]["kappa"],
                "auto_vs_clinician": agreement,
                "inter_rater": inter,
                "mean_quality_rating": _r(rv["quality_rating"].dropna().mean(), 2),
                "status": status}

    @staticmethod
    def _inter_rater(rated: pd.DataFrame) -> Dict[str, Any]:
        """Fleiss' kappa over items sharing the most common rater count k >= 3; Cohen's kappa for 2 raters."""
        per_item = rated.groupby("run_id")["reviewer_id"].nunique()
        multi = per_item[per_item >= 2]
        if multi.empty:
            return {"status": "insufficient_data: no item has two or more clinician ratings",
                    "method": None, "kappa": None, "n_items": 0, "n_raters": 0}
        three_plus = multi[multi >= 3]
        if len(three_plus) >= 2:
            k = int(three_plus.value_counts().idxmax())
            items = three_plus[three_plus == k].index
            sub = rated[rated["run_id"].isin(items)].drop_duplicates(["run_id", "reviewer_id"])
            table = [[int((g["diagnosis_verdict"] == c).sum()) for c in REVIEW_CATEGORIES]
                     for _, g in sub.groupby("run_id")]
            kappa = fleiss_kappa(table)
            return {"status": "ok", "method": "fleiss", "kappa": _r(kappa, 3), "n_items": len(table),
                    "n_raters": k, "categories": list(REVIEW_CATEGORIES)}
        # Two raters: the reviewer pair with the most shared items.
        wide = rated.pivot_table(index="run_id", columns="reviewer_id", values="diagnosis_verdict", aggfunc="first")
        best = None
        cols = list(wide.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                shared = wide[[cols[i], cols[j]]].dropna()
                if best is None or len(shared) > len(best):
                    best = shared
        if best is None or len(best) < 2:
            return {"status": "insufficient_data: fewer than 2 items rated by the same two clinicians",
                    "method": None, "kappa": None, "n_items": 0 if best is None else len(best), "n_raters": 2}
        kappa = cohens_kappa_categorical(best.iloc[:, 0].tolist(), best.iloc[:, 1].tolist())
        return {"status": "ok", "method": "cohen", "kappa": _r(kappa, 3), "n_items": int(len(best)), "n_raters": 2,
                "categories": list(REVIEW_CATEGORIES)}

    def clinician_protocol(self, n: int = 50, seed: int = 42) -> Dict[str, Any]:
        """A fixed, blinded, stratified set of run_ids for the clinician-review protocol.

        Strata are dataset x (V1 correct / wrong); within each stratum runs are ordered by a
        seeded hash and allocated proportionally (largest remainder). Closed-loop rows are excluded.
        The variant is omitted from the output so the file itself does not unblind reviewers.
        """
        df = self.runs[self.runs["gold_valid"] & ~self.runs["variant_id"].astype(str).str.endswith("-CL")].copy()
        if df.empty:
            return {"n": 0, "run_ids": [], "status": "insufficient_data: no scorable runs"}
        df["stratum"] = df["dataset"].astype(str) + "|" + np.where(df["correct"], "correct", "wrong")
        df["order"] = [hashlib.sha256(f"{seed}:{rid}".encode()).hexdigest() for rid in df["run_id"]]
        sizes = df["stratum"].value_counts().sort_index()
        n = min(n, len(df))
        quota = sizes / sizes.sum() * n
        alloc = np.floor(quota).astype(int)
        for s in (quota - alloc).sort_values(ascending=False).index[: n - int(alloc.sum())]:
            alloc[s] += 1
        picked = []
        for stratum, k in alloc.items():
            g = df[df["stratum"] == stratum].sort_values("order")
            # One run per case where possible so reviewers see distinct vignettes.
            g = pd.concat([g.drop_duplicates("case_id"), g[g.duplicated("case_id")]])
            picked.extend(g.head(int(k))[["run_id", "case_id", "stratum"]].to_dict("records"))
        picked.sort(key=lambda r: hashlib.sha256(f"{seed}:order:{r['run_id']}".encode()).hexdigest())
        return {"n": len(picked), "seed": seed, "db_path": self.db_path,
                "strata": {s: int(k) for s, k in alloc.items()},
                "blinding": "variant_id withheld; items listed in seeded random order",
                # Strata are not listed per item: the correct/wrong label would unblind the reviewer.
                "items": [{"run_id": int(r["run_id"]), "case_id": r["case_id"]} for r in picked]}

    # ------------------------------------------------------------------ report
    def headline_findings(self, rep: Dict[str, Any]) -> List[str]:
        f: List[str] = []
        m = rep["measurement_validity"]
        f.append(f"Reported accuracy {m['reported_accuracy_mean']} is inflated by substring matching: "
                 f"{m['runs_with_unparsed_diagnosis']} runs with an unparsed (empty) diagnosis scored "
                 f"{m['reported_accuracy_on_unparsed_runs']}, and {m['runs_with_option_letter_diagnosis']} runs whose "
                 f"'diagnosis' is a bare option letter ({m['cases_total'] - m['cases_with_answer_key']}/{m['cases_total']} "
                 f"cases contain no options, so a letter is a non-answer) scored "
                 f"{m['reported_accuracy_on_option_letter_runs']}. With recovered outputs and whole-word matching, "
                 f"accuracy is {m['corrected_accuracy_mean_all_cases']}.")
        f.append(f"Only {m['cases_with_valid_gold']} of {m['cases_total']} gold labels are real diagnoses; the rest are "
                 f"templated titles. On scorable cases accuracy is {m['corrected_accuracy_mean_valid_gold']}.")
        changes = [v["diagnosis_changed_vs_v1_pct"] for v in rep["variants"] if v["variant_id"] != "V1"]
        if changes:
            f.append(f"Open-loop governance changed the primary diagnosis in at most {max(changes)}% of cases: "
                     "the layers annotate but do not alter clinical decisions.")
        acc_tests = [t for t in rep["paired_tests"] if t["metric"] == "accuracy"]
        if acc_tests and all(t["wilcoxon_p"] >= 0.05 for t in acc_tests):
            f.append("No governed variant differs from baseline in diagnostic accuracy (paired Wilcoxon, all p >= 0.05).")
        mc = rep["accuracy_tests"]
        if mc:
            sig = [t for t in mc if (t.get("mcnemar_exact_p_holm") or 1.0) < ALPHA]
            lo = min(t["mcnemar_exact_p"] for t in mc)
            f.append(f"Exact McNemar on binary correctness vs V1: {len(sig)} of {len(mc)} comparisons significant after "
                     f"Holm-Bonferroni over {rep['multiple_comparisons']['family_size']} paired tests (smallest raw p "
                     f"{lo}); accuracy differences range {min(t['accuracy_diff'] for t in mc)} to "
                     f"{max(t['accuracy_diff'] for t in mc)}.")
        for t in rep.get("closed_loop_effect") or []:
            f.append(f"Closed vs open loop ({t['comparison']}, n={t['n_pairs']}): accuracy {t['accuracy_open']} -> "
                     f"{t['accuracy_closed']}; revision fixed {t['fixed_by_revision']} and broke "
                     f"{t['broken_by_revision']} answers (exact McNemar p={t['mcnemar_exact_p']}, "
                     f"Holm {t['mcnemar_exact_p_holm']}).")
        shares = [a["share_of_drop_from_detector_penalties"] for a in rep["audit_paradox"]
                  if a["share_of_drop_from_detector_penalties"] is not None and a["reported_quality_drop"] > 0.01]
        if shares:
            f.append(f"{min(shares) * 100:.0f}-{max(shares) * 100:.0f}% of each governed variant's reported quality drop "
                     "comes from penalizing its own detectors: the 'Audit Paradox' is a scoring artifact.")
        aucs = [a for a in rep["alert_discrimination"] if a["auroc"] is not None]
        if aucs:
            best = max(aucs, key=lambda a: a["auroc"])
            if best["auroc"] < 0.65:
                f.append(f"No governance signal detects misdiagnosis meaningfully better than chance: AUROCs range "
                         f"{min(a['auroc'] for a in aucs)}-{best['auroc']} (0.5 = chance).")
            else:
                f.append(f"Best governance signal for detecting misdiagnosis: {best['signal']} in {best['variant_id']} "
                         f"(AUROC {best['auroc']}; 0.5 = chance).")
        always = [a for a in rep["alert_discrimination"] if a["signal"] == "safety_alerts" and a["fire_rate"] == 1.0]
        if always:
            f.append("The safety validator raised at least one alert on 100% of runs, so alert presence carries no "
                     "information about whether the diagnosis is wrong.")
        rp = rep["alert_reproducibility"]
        if rp:
            f.append(f"Same validator, same cached diagnosis (V4 vs V5): identical alert counts in only "
                     f"{rp['identical_alert_count_pct']}% of cases (Spearman {rp['alert_count_spearman']}).")
        wrong_n = rep["failure_taxonomy"]["misdiagnosed_cases_v1"]
        pw = (rep["power_analysis"] or {}).get("pooled") or {}
        if pw.get("min_detectable_accuracy_diff") is not None:
            f.append(f"Power: with {pw['n_pairs']} paired cases and {pw['discordance_rate']} mean discordance, the "
                     f"smallest accuracy difference detectable at alpha 0.05 / power 0.8 is "
                     f"{pw['min_detectable_accuracy_diff']}; a 5-point difference needs "
                     f"{pw['required_n_for_5pt_diff'] or 'more'} pairs ({wrong_n} baseline misdiagnoses).")
        else:
            grid = (rep["power_analysis"] or {}).get("required_n_for_5pt_diff_by_assumed_discordance", {})
            f.append(f"Statistical power is limited: {m['cases_with_valid_gold']} scorable cases and {wrong_n} baseline "
                     f"misdiagnoses, and variants disagree with V1 on only {pw.get('discordance_rate')} of cases, so no "
                     f"accuracy difference is detectable at alpha 0.05 / power 0.8. Detecting a 5-point difference needs "
                     + ", ".join(f"{v} pairs at {k} discordance" for k, v in grid.items()) + ".")
        if not rep["jru_measurement"]["n_runs_measured"]:
            f.append("JRU is not reported as a measurement: no run was scored by a judge model different from the "
                     "generator.")
        c = rep["calibration"]
        if c.get("n"):
            f.append(f"Model-reported diagnosis probability: ECE {c['ece']}, Brier {c['brier']} (n={c['n']}).")
        lat = rep["latency_by_agent"]
        if lat:
            f.append(f"Latency bottleneck: {lat[0]['agent']} (mean {lat[0]['mean_s']}s, p95 {lat[0]['p95_s']}s).")
        if rep["integrity"]["notes"]:
            f.append("Integrity: " + " ".join(rep["integrity"]["notes"]))
        return f

    def report(self) -> Dict[str, Any]:
        rep: Dict[str, Any] = {
            "generated_at": time.time(),
            "db_path": self.db_path,
            "n_runs_analyzed": int(len(self.runs)),
            "n_cases": int(self.runs["case_id"].nunique()),
            "models": sorted(set(self.raw_runs["provider"] + " / " + self.raw_runs["model"])),
            "integrity": self.integrity_audit(),
            "measurement_validity": self.measurement_validity(),
            "variants": self.variant_summary(),
            "paired_tests": self.paired_tests(),
            "accuracy_tests": self.accuracy_tests(),
            "closed_loop_effect": self.closed_loop_effect(),
            "audit_paradox": self.audit_paradox(),
            "alert_discrimination": self.alert_discrimination(),
            "alert_reproducibility": self.alert_reproducibility(),
            "hitl": self.hitl_analysis(),
            "calibration": self.calibration(),
            "latency_by_agent": self.latency_by_agent(),
            "strata": self.strata(),
            "failure_taxonomy": self.failure_taxonomy(),
            "clinician_validation": self.clinician_validation(),
            "jru_measurement": self.jru_measurement(),
            "limitations": [
                "Single model (one provider); results may not transfer to other LLMs.",
                "Variants ran concurrently against one endpoint, so per-call latency includes contention.",
                "Accuracy uses lenient string matching against gold labels; only non-templated labels are scored.",
                "Governance outputs are not validated against clinicians until reviews are collected.",
            ],
        }
        rep["multiple_comparisons"] = self.apply_holm(rep["paired_tests"], rep["accuracy_tests"])
        rep["power_analysis"] = self.power_analysis(rep["accuracy_tests"])
        rep["headline_findings"] = self.headline_findings(rep)
        return rep
