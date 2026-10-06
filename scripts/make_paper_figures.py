#!/usr/bin/env python3
"""Draw the manuscript figures from the measured analysis (results/rigor_report.json).

Every plotted value is read from the report written by ``govbench-rigor``; nothing is typed in by hand.
Run ``uv run govbench-rigor`` first, then ``uv run python -m scripts.make_paper_figures``.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "results" / "rigor_report.json"
MEDQA_REPORT = ROOT / "results" / "rigor_report_medqa.json"
OUT = ROOT / "paper" / "figures"

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight",
})
GREY, BLUE, ORANGE, GREEN = "#6b7280", "#1d4ed8", "#c2410c", "#15803d"


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300)
    plt.close(fig)
    print(f"wrote paper/figures/{name}.pdf")


def architecture():
    fig, ax = plt.subplots(figsize=(7.0, 2.3))
    ax.set_xlim(0, 12.6)
    ax.set_ylim(0, 6.6)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=color, ec="#374151", lw=0.6))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7)

    def arrow(x1, y1, x2, y2, color="#374151", ls="-"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=0.6, color=color, linestyle=ls))

    box(0.0, 2.3, 1.4, 0.9, "Case\ntext", "#f3f4f6")
    box(1.8, 2.3, 1.5, 0.9, "Research\n(extract)", "#dbeafe")
    box(3.7, 2.3, 1.5, 0.9, "Diagnosis\n(differential)", "#dbeafe")
    arrow(1.4, 2.75, 1.8, 2.75)
    arrow(3.3, 2.75, 3.7, 2.75)
    # Parallel checks: each reads only the case and the diagnosis.
    parallel = [(4.3, "Grounding verifier"), (2.4, "Safety validator"), (0.5, "Consistency checker")]
    for y, label in parallel:
        box(5.9, y, 2.3, 0.7, label, "#fef3c7")
        arrow(5.2, 2.75, 5.9, y + 0.35)
    ax.text(7.05, 0.05, "parallel checks", ha="center", fontsize=6.3, color="#6b7280")
    # The simulated attending runs after them and also reads the safety findings.
    box(8.55, 2.25, 1.9, 1.0, "Attending\nsimulator", "#fde68a")
    arrow(8.2, 2.75, 8.55, 2.75)
    box(10.9, 2.15, 1.7, 1.2, "Rules +\ndecision\nsupport", "#dcfce7")
    arrow(10.45, 2.75, 10.9, 2.75)
    for y, _ in (parallel[0], parallel[2]):
        arrow(8.2, y + 0.35, 10.9, 2.75)
    # Closed-loop feedback, drawn above the checks.
    ax.plot([9.5, 9.5, 4.45], [3.25, 6.0, 6.0], color=ORANGE, lw=0.6, ls="--")
    arrow(4.45, 6.0, 4.45, 3.2, color=ORANGE, ls="--")
    ax.text(4.6, 6.15, "closed loop only: any blocking finding \u2192 one bounded revision, then re-check",
            fontsize=5.8, color=ORANGE)
    _save(fig, "architecture")


def audit_paradox(r):
    variants = r["variants"]
    ids = [v["variant_id"] for v in variants]
    x = list(range(len(ids)))
    w = 0.26
    fig, ax = plt.subplots(figsize=(3.45, 1.75))
    ax.bar([i - w for i in x], [v["reported_quality"] for v in variants], w,
           label="Reported rubric quality", color=GREY)
    ax.bar(x, [v["detector_neutral_quality"] for v in variants], w,
           label="Detector-neutral quality", color=BLUE)
    ax.bar([i + w for i in x], [v["accuracy_valid_gold"] for v in variants], w,
           label="Accuracy (scorable cases)", color=GREEN)
    ax.set_xticks(x)
    ax.set_xticklabels([f"G{int(i[1]) - 1}\n({i})" for i in ids])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, fontsize=6)
    _save(fig, "audit_paradox")


def alert_auroc(r):
    rows = r["alert_discrimination"]
    labels = [f"{a['signal'].replace('_', ' ')} ({a['variant_id']})" for a in rows]
    vals = [a["auroc"] for a in rows]
    y = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(3.45, 1.8))
    ax.hlines(y, 0.5, vals, color="#9ca3af", lw=0.8)
    ax.plot(vals, y, "o", color=ORANGE, ms=3.5)
    ax.axvline(0.5, color="#111827", lw=0.6, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0.3, 0.7)
    ax.set_xlabel("AUROC for a wrong primary diagnosis (0.5 = chance)")
    ax.invert_yaxis()
    _save(fig, "alert_auroc")


def calibration(r):
    cal = r["calibration"]
    bins = cal["bins"]
    fig, ax = plt.subplots(figsize=(1.9, 1.75))
    ax.plot([0, 1], [0, 1], ls="--", color="#111827", lw=0.6)
    ax.scatter([b["mean_confidence"] for b in bins], [b["observed_accuracy"] for b in bins],
               s=[6 + 4 * b["n"] for b in bins], color=BLUE, alpha=0.75, edgecolor="none")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Stated probability")
    ax.set_ylabel("Observed accuracy")
    ax.set_title(f"ECE {cal['ece']:.2f}, n={cal['n']}")
    _save(fig, "calibration")


def closed_loop(r):
    labels = {"V1": "G0\nnone", "V5": "G4\nopen", "V2-CL": "Verifier\nclosed", "V3-CL": "Attending\nclosed",
              "V4-CL": "Safety\nclosed", "V5-CL": "G4\nclosed"}
    acc = {v["variant_id"]: v["accuracy_valid_gold"] for v in r["variants"]}
    order = [v for v in labels if v in acc]
    rev = {t["variant_id"]: t for t in r["revision_by_variant"]}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 1.9), gridspec_kw={"width_ratios": [1.4, 1]})
    ax1.bar(range(len(order)), [acc[v] for v in order],
            color=[GREY if not v.endswith("-CL") else BLUE for v in order])
    ax1.axhline(acc["V1"], color="#111827", lw=0.6, ls="--")
    ax1.set_xticks(range(len(order)))
    ax1.set_xticklabels([labels[v] for v in order], fontsize=6)
    ax1.set_ylim(0, 0.6)
    ax1.set_ylabel("Accuracy (MedQA, n=300)")
    cl = [v for v in order if v in rev]
    x = range(len(cl))
    ax2.bar([i - 0.2 for i in x], [rev[v]["within_run_fixed"] for v in cl], 0.4, label="fixed", color=GREEN)
    ax2.bar([i + 0.2 for i in x], [rev[v]["within_run_broken"] for v in cl], 0.4, label="broken", color=ORANGE)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels([labels[v] for v in cl], fontsize=6)
    ax2.set_ylabel("Answers changed by revision")
    ax2.legend(frameon=False, fontsize=6)
    _save(fig, "closed_loop")


def main():
    report = json.loads(REPORT.read_text())
    if MEDQA_REPORT.exists():
        closed_loop(json.loads(MEDQA_REPORT.read_text()))
    architecture()
    audit_paradox(report)
    alert_auroc(report)
    calibration(report)


if __name__ == "__main__":
    main()
