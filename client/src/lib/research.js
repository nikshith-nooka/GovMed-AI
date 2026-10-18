// Adapters from the analysis report (/api/research/findings) to chart rows. Pure functions, no fetching: every
// value comes from the report of the experiment selected in the top bar; nothing is filled in when it is missing.
import { VARIANT_LABELS } from './api';

/** 95% Wilson score interval for a proportion p observed on n trials. */
export function wilson(p, n, z = 1.96) {
  if (p == null || !n) return [null, null];
  const denom = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / denom;
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

export const isClosed = (id) => String(id).endsWith('-CL');
export const variantLabel = (id) => (VARIANT_LABELS[id] || id).replace(/^V\d(-CL)? · /, '');

/** Each configuration was run once per scorable case, so its accuracy is a proportion over that many cases. */
export const scorableCases = (report) => report?.measurement_validity?.cases_with_valid_gold ?? null;

export function accuracyRows(report) {
  const n = scorableCases(report);
  return (report?.variants || []).map((v) => {
    const [lo, hi] = wilson(v.accuracy_valid_gold, n);
    return { id: v.variant_id, label: `${v.variant_id} · ${variantLabel(v.variant_id)}`, value: v.accuracy_valid_gold,
      lo, hi, group: isClosed(v.variant_id) ? 'closed' : 'open' };
  });
}

export function frontierPoints(report, key) {
  return accuracyRows(report).map((r) => ({ ...r, y: r.value, x: (report.variants.find((v) => v.variant_id === r.id) || {})[key] ?? null }));
}

export function forestRows(report) {
  return (report?.accuracy_tests || []).map((t) => {
    const id = t.comparison.split(' - ')[0];
    return { id, label: `${id} · ${variantLabel(id)}`, diff: t.accuracy_diff, lo: t.accuracy_diff_ci95_low,
      hi: t.accuracy_diff_ci95_high, p: t.mcnemar_exact_p, pAdj: t.mcnemar_exact_p_holm };
  });
}

export function revisionRows(report) {
  return (report?.revision_by_variant || []).map((r) => ({ id: r.variant_id, label: `${r.variant_id} · ${variantLabel(r.variant_id)}`,
    fixed: r.within_run_fixed, broken: r.within_run_broken, p: r.sign_test_p }));
}

export function overheadMetrics(report) {
  const vs = report?.variants || [];
  const values = (key) => vs.map((v) => ({ id: v.variant_id, label: VARIANT_LABELS[v.variant_id] || v.variant_id,
    value: v[key] ?? null, group: isClosed(v.variant_id) ? 'closed' : 'open' }));
  return [
    { key: 'calls', title: 'Model calls per case', fmt: (v) => v.toFixed(1), values: values('model_calls_mean') },
    { key: 'tokens', title: 'Tokens per case', fmt: (v) => Math.round(v).toLocaleString(), values: values('tokens_mean') },
    { key: 'gov', title: 'Governance-only latency, median (s)', fmt: (v) => v.toFixed(1), values: values('governance_latency_p50_s') },
  ];
}
