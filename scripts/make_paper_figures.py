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
# Paired rerun: closed-loop runs reuse the open-loop diagnosis (the earlier pass regenerated it).
MEDQA_REPORT = ROOT / "results" / "rigor_report_medqa_paired.json"
OUT = ROOT / "paper" / "figures"

plt.rcParams.update({
    # STIX is Times-compatible (matches the IEEEtran body) and ships with matplotlib; Type 42 embeds it as
    # TrueType instead of Type 3, which IEEE PDF checks reject.
    "font.family": "serif", "font.serif": ["STIXGeneral"], "mathtext.fontset": "stix",
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "legend.fontsize": 7.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})
GREY, BLUE, ORANGE, GREEN = "#6b7280", "#1d4ed8", "#c2410c", "#15803d"
# Open vs closed loop and fixed vs broken must stay distinct in grayscale print: light vs dark fill plus hatching.
LIGHT_GREY, DARK_BLUE, INK = "#c7cad1", "#1f3f8f", "#1f2937"
FULL_WIDTH = 7.16  # IEEE two-column \textwidth in inches; figure* floats are placed at this width


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300)
    plt.close(fig)
    print(f"wrote paper/figures/{name}.pdf")


def architecture():
    """The G4 workflow as implemented in src/pipeline/orchestrator.py (G1-G3 enable a single check)."""
    fig = plt.figure(figsize=(FULL_WIDTH, 2.2))
    ax = fig.add_axes((0, 0, 1, 1))  # data units map onto the full width, so 1 unit = FULL_WIDTH / 14.4 in
    ax.set_xlim(0, 14.4)
    ax.set_ylim(0.55, 6.1)
    ax.axis("off")
    io, agent, check, rev = "#f3f4f6", "#e3ebf8", "#fdf3d8", "#fbe4d5"

    def box(x, y, w, h, text, color, ls="-", **kw):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1",
                                    fc=color, ec=INK, lw=0.6, ls=ls))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.5, linespacing=1.1, **kw)

    def line(xs, ys, color=INK, ls="-", head=True):
        if len(xs) > 2:
            ax.plot(xs[:-1], ys[:-1], color=color, lw=0.7, ls=ls, solid_capstyle="butt")
        if head:
            ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]),
                        arrowprops=dict(arrowstyle="-|>", lw=0.7, color=color, linestyle=ls,
                                        shrinkA=0, shrinkB=0, mutation_scale=7))
        else:
            ax.plot(xs[-2:], ys[-2:], color=color, lw=0.7, ls=ls)

    mid = 3.0
    box(0.05, mid - 0.4, 1.15, 0.8, "Clinical\ncase", io)
    box(1.5, mid - 0.4, 1.35, 0.8, "Research\nagent", agent)
    box(3.15, mid - 0.4, 1.4, 0.8, "Diagnosis\nagent", agent)
    line([1.2, 1.5], [mid, mid])
    line([2.85, 3.15], [mid, mid])
    ax.text(3.85, mid - 0.55, "first answer", ha="center", va="top", fontsize=6.8, color=GREY, style="italic")

    # Parallel checks fan out from one bus: each runs on the same first answer.
    checks = [(4.65, "Grounding verifier"), (mid, "Safety validator"), (1.35, "Consistency checker")]
    bus_in, cx, cw = 4.82, 5.1, 2.2
    line([4.55, bus_in], [mid, mid], head=False)
    ax.plot([bus_in, bus_in], [checks[2][0], checks[0][0]], color=INK, lw=0.7)
    for y, label in checks:
        box(cx, y - 0.32, cw, 0.64, label, check)
        line([bus_in, cx], [y, y])
    ax.text(cx + cw / 2, 0.92, "parallel checks", ha="center", va="top", fontsize=6.8, color=GREY, style="italic")

    # The simulated attending runs after the checks and reads the safety findings.
    ax_x, ax_w = 7.6, 1.65
    box(ax_x, mid - 0.4, ax_w, 0.8, "Attending\nreviewer (sim.)", check)
    line([cx + cw, ax_x], [mid, mid])
    # Every finding (verifier, consistency, attending) reaches the revision decision.
    bus_out = 9.5
    line([cx + cw, bus_out], [checks[0][0]] * 2, head=False)
    line([cx + cw, bus_out], [checks[2][0]] * 2, head=False)
    ax.plot([bus_out, bus_out], [checks[2][0], checks[0][0]], color=INK, lw=0.7)
    line([ax_x + ax_w, bus_out], [mid, mid], head=False)

    gx, gw = 9.75, 1.4
    box(gx, mid - 0.45, gw, 0.9, "Blocking\nfinding?", io)
    line([bus_out, gx], [mid, mid])

    fx, fw = 11.6, 1.3
    box(fx, mid - 0.45, fw, 0.9, "Final answer\n+ rule flags", io)
    line([gx + gw, fx], [mid, mid])
    ax.text((gx + gw + fx) / 2, mid + 0.06, "no", ha="center", va="bottom", fontsize=6.8, color=GREY)

    ex, ew = 13.15, 1.2
    box(ex, mid - 0.45, ew, 0.9, "Scorer\n(answer key)", io, ls="--")
    line([fx + fw, ex], [mid, mid])

    # Closed loop only: exactly one revision, then a re-check that cannot trigger a second revision.
    ry, rh = 5.05, 0.85
    gc, fc = gx + gw / 2, fx + fw / 2
    box(gc - 1.0, ry, 2.0, rh, "One revision\n(diagnosis agent)", rev, ls="--")
    box(11.75, ry, 2.4, rh, "Re-check: verifier +\nsafety (if enabled)", rev, ls="--")
    line([gc, gc], [mid + 0.45, ry], color=ORANGE, ls="--")
    ax.text(gc + 0.1, (mid + 0.45 + ry) / 2, "yes (closed\nloop only)", ha="left", va="center",
            fontsize=6.8, color=ORANGE, linespacing=1.0)
    line([gc + 1.0, 11.75], [ry + rh / 2] * 2, color=ORANGE, ls="--")
    line([fc, fc], [ry, mid + 0.45], color=ORANGE, ls="--")
    ax.text(fc + 0.1, (mid + 0.45 + ry) / 2, "no second\nrevision", ha="left", va="center",
            fontsize=6.8, color=ORANGE, linespacing=1.0)
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


# Same names as Table I of the NCRTHT paper (G1 verifier, G2 attending reviewer, G3 safety validator).
CONFIG_LABELS = {"V1": "G0", "V5": "G4 open", "V2-CL": "G1 closed", "V3-CL": "G2 closed",
                 "V4-CL": "G3 closed", "V5-CL": "G4 closed"}


def closed_loop(r):
    labels = {"V1": "G0\n(no checks)", "V5": "G4 open\n(all checks)", "V2-CL": "G1 closed\n(verifier)",
              "V3-CL": "G2 closed\n(attending)", "V4-CL": "G3 closed\n(safety)", "V5-CL": "G4 closed\n(all checks)"}
    var = {v["variant_id"]: v for v in r["variants"]}
    order = [v for v in labels if v in var]
    rev = {t["variant_id"]: t for t in r["revision_by_variant"]}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL_WIDTH, 2.0), gridspec_kw={"width_ratios": [1.45, 1]})
    accs = [var[v]["accuracy_valid_gold"] for v in order]
    cis = [_wilson(var[v]["accuracy_valid_gold"], var[v]["n_runs"]) for v in order]
    ax1.bar(range(len(order)), accs, 0.62, color=[DARK_BLUE if v.endswith("-CL") else LIGHT_GREY for v in order],
            edgecolor=INK, lw=0.5, yerr=[[a - lo for a, (lo, _) in zip(accs, cis)], [hi - a for a, (_, hi) in zip(accs, cis)]],
            error_kw=dict(lw=0.7, capsize=2, ecolor=INK))
    for i, (a, (_, hi)) in enumerate(zip(accs, cis)):
        ax1.text(i, hi + 0.012, f"{a * 100:.1f}%", ha="center", va="bottom", fontsize=6.5)
    ax1.axhline(var["V1"]["accuracy_valid_gold"], color=INK, lw=0.6, ls="--")
    ax1.set_xticks(range(len(order)))
    ax1.set_xticklabels([labels[v] for v in order], fontsize=6.8, linespacing=1.0)
    ax1.set_ylim(0, 0.6)
    ax1.set_ylabel("Accuracy, 95% CI (n = 300)")
    cl = [v for v in order if v in rev]
    x = range(len(cl))
    fixed = [rev[v]["within_run_fixed"] for v in cl]
    broken = [rev[v]["within_run_broken"] for v in cl]
    ax2.bar([i - 0.2 for i in x], fixed, 0.4, label="fixed (wrong → right)", color=GREEN, edgecolor=INK, lw=0.5)
    ax2.bar([i + 0.2 for i in x], broken, 0.4, label="broken (right → wrong)", color="#f2c2a4",
            edgecolor=INK, lw=0.5, hatch="////")
    for i, (f, b) in enumerate(zip(fixed, broken)):
        ax2.text(i - 0.2, f + 0.6, str(f), ha="center", va="bottom", fontsize=6.5)
        ax2.text(i + 0.2, b + 0.6, str(b), ha="center", va="bottom", fontsize=6.5)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels([labels[v] for v in cl], fontsize=6.8, linespacing=1.0)
    ax2.set_ylim(0, max(broken + fixed) * 1.2)
    ax2.set_ylabel("Revised answers")
    ax2.legend(frameon=False, fontsize=6.8, loc="upper left", handlelength=1.4)
    plt.rcParams["hatch.linewidth"] = 0.5
    fig.tight_layout(w_pad=1.5)
    _save(fig, "closed_loop")


def _wilson(p, n, z=1.96):
    """95% Wilson score interval for a proportion (computed from the reported accuracy and n)."""
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return centre - half, centre + half


def tradeoff(r):
    """Accuracy against mean tokens and median summed latency, one marker per configuration."""
    # Distinct markers plus one legend: the single-check points sit too close together for text labels,
    # and shapes stay distinguishable in grayscale print.
    style = {"V1": ("o", GREY), "V5": ("s", GREY), "V2-CL": ("^", DARK_BLUE),
             "V3-CL": ("D", DARK_BLUE), "V4-CL": ("v", DARK_BLUE), "V5-CL": ("P", DARK_BLUE)}
    style = {k: (CONFIG_LABELS[k], *s) for k, s in style.items()}
    by_id = {v["variant_id"]: v for v in r["variants"]}
    rows = [by_id[k] for k in style if k in by_id]  # legend order: open loop first, then G1-G4 closed
    fig, axes = plt.subplots(1, 2, figsize=(FULL_WIDTH, 2.0), sharey=True)
    for ax, key, xlabel in ((axes[0], "tokens_mean", "Mean tokens per question"),
                            (axes[1], "e2e_latency_p50_s", "Median summed latency (s)")):
        for v in rows:
            label, marker, colour = style[v["variant_id"]]
            acc, n = v["accuracy_valid_gold"], v["n_runs"]
            lo, hi = _wilson(acc, n)
            ax.errorbar(v[key], acc, yerr=[[acc - lo], [hi - acc]], fmt=marker, color=colour, ms=4.5, lw=0.8,
                        capsize=2, label=label, mec=INK, mew=0.4)
        ax.axhline(by_id["V1"]["accuracy_valid_gold"], color=INK, lw=0.6, ls="--")
        ax.set_xlabel(xlabel)
    axes[0].set_xlim(0, None)
    axes[1].set_xlim(0, None)
    axes[0].set_ylabel("Accuracy, 95% CI (n = 300)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.tight_layout(w_pad=2.0)
    fig.legend(handles, labels, loc="lower center", ncol=len(rows), frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, 0.98), handletextpad=0.3, columnspacing=1.4)
    _save(fig, "tradeoff")


def main():
    report = json.loads(REPORT.read_text())
    if MEDQA_REPORT.exists():
        medqa = json.loads(MEDQA_REPORT.read_text())
        closed_loop(medqa)
        tradeoff(medqa)
    architecture()
    audit_paradox(report)
    alert_auroc(report)
    calibration(report)


if __name__ == "__main__":
    main()
