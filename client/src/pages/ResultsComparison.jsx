import React, { useEffect, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js';
import { FlaskConical, Loader2 } from 'lucide-react';
import { CHART, VARIANT_LABELS, findingsPath, fmt, useApi, useExperiment, variantTicks } from '../lib/api';
import { DivergingBars, ForestPlot, Frontier, SmallMultiples, DotPlotCI } from '../components/charts';
import { accuracyRows, forestRows, frontierPoints, overheadMetrics, revisionRows } from '../lib/research';
import { CONFIG_LEGEND } from './Dashboard';
import FindingsPanel from './FindingsPanel';
import './clinical.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const TABS = [
  ['variants', 'Variant comparison'],
  ['cost', 'Cost & latency'],
  ['signals', 'Governance signals'],
  ['closed', 'Closed-loop revision'],
  ['stats', 'Paired statistics'],
  ['findings', 'Findings & validity'],
];
const TAB_IDS = TABS.map(([id]) => id);
const tabFromUrl = () => {
  const t = new URLSearchParams(window.location.search).get('tab');
  return TAB_IDS.includes(t) ? t : 'variants';
};
const pval = (v) => (v == null ? '—' : v < 0.001 ? '<0.001' : v.toFixed(3));
const pctOf = (v) => (v == null ? '—' : `${(v * 100).toFixed(1)}%`);

function Table({ rows, cols }) {
  return (
    <div className="cw-table-wrap">
      <table className="cw-table">
        <thead><tr>{cols.map(([k, label]) => <th key={k}>{label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{cols.map(([k, , d, f]) => <td key={k} className="cw-num">{f ? f(r[k], r) : (typeof r[k] === 'number' ? fmt(r[k], d ?? 3) : fmt(r[k]))}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const barOptions = (yTitle, max, xTicks = variantTicks) => ({
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' } },
  scales: { x: { ticks: xTicks }, y: { beginAtZero: true, ...(max ? { max } : {}), title: { display: true, text: yTitle } } },
});

export default function ResultsComparison() {
  // The tab lives in the URL (?tab=) so the Overview can link to it and reloads keep it.
  const [tab, setTabState] = useState(tabFromUrl);
  useEffect(() => {
    const sync = () => setTabState(tabFromUrl());
    window.addEventListener('popstate', sync);
    window.addEventListener('govbench:navigate', sync);
    return () => { window.removeEventListener('popstate', sync); window.removeEventListener('govbench:navigate', sync); };
  }, []);
  const setTab = (id) => {
    setTabState(id);
    window.history.replaceState(window.history.state, '', `${window.location.pathname}?tab=${id}`);
  };
  const experiment = useExperiment();
  const { data: r, error, loading } = useApi(findingsPath(experiment));

  if (loading) return <div className="cw-page cw-empty"><Loader2 className="spin" /> Loading…</div>;
  if (error) return <div className="cw-page"><div className="cw-banner info"><FlaskConical size={18} /><div><strong>No analysis yet</strong>{error}</div></div></div>;

  const labels = r.variants.map((v) => (VARIANT_LABELS[v.variant_id] || v.variant_id).split(' · '));
  const signals = r.alert_discrimination;

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Benchmark Results</h2>
          <p className="cw-sub">{r.n_runs_analyzed} runs, {r.n_cases} cases, {(r.models || []).join(', ')}. Accuracy is computed on the {r.measurement_validity.cases_with_valid_gold} cases with a scorable gold label{r.measurement_validity.cases_with_answer_key === r.measurement_validity.cases_total ? ' (exact answer key)' : ''}.</p>
        </div>
      </div>
      <div className="cw-tabs cw-seg" role="tablist" style={{ display: 'inline-flex' }}>
        {TABS.filter(([id]) => id !== 'closed' || r.revision_by_variant?.length).map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}
      </div>

      {tab === 'variants' && (
        <>
          <div className="cw-card">
            <DotPlotCI rows={accuracyRows(r)} reference={r.variants.find((v) => v.variant_id === 'V1')?.accuracy_valid_gold}
              xLabel="Accuracy (axis fitted to data)" title="Diagnostic accuracy by configuration"
              subtitle={`95% Wilson intervals over ${r.measurement_validity.cases_with_valid_gold} scorable cases; dashed line = G0`}
              legend={CONFIG_LEGEND} summary={r.variants.map((v) => `${v.variant_id} ${fmt(v.accuracy_valid_gold)}`).join(', ')} />
          </div>
          <div className="cw-card">
            <h3>Accuracy and two quality scores</h3>
            <div style={{ height: 300 }}>
              <Bar options={barOptions('Score (0-1)', 1)} data={{ labels, datasets: [
                { label: 'Accuracy (scorable cases)', data: r.variants.map((v) => v.accuracy_valid_gold), backgroundColor: CHART.primary },
                { label: 'Detector-neutral quality', data: r.variants.map((v) => v.detector_neutral_quality), backgroundColor: CHART.secondary },
                { label: 'Reported quality', data: r.variants.map((v) => v.reported_quality), backgroundColor: CHART.muted },
              ] }} />
            </div>
            <p className="cw-muted" style={{ marginTop: 8 }}>Reported quality subtracts points for flags raised by a variant's own detectors, so it falls as checks are added even when the diagnosis is unchanged.</p>
          </div>
          <div className="cw-card">
            <Table rows={r.variants} cols={[
              ['variant_id', 'Variant', null, (v) => VARIANT_LABELS[v] || v],
              ['accuracy_valid_gold', 'Accuracy'], ['detector_neutral_quality', 'Detector-neutral'], ['reported_quality', 'Reported'],
              ['diagnosis_changed_vs_v1_pct', 'Dx changed vs V1 (%)', 1],
              ['hallucination_flags_total', 'Hallucination flags', 0], ['safety_alerts_total', 'Safety alerts', 0],
            ]} />
          </div>
        </>
      )}

      {tab === 'cost' && (
        <>
          <div className="cw-two">
            <div className="cw-card">
              <Frontier points={frontierPoints(r, 'tokens_mean')} xLabel="Mean tokens per case" yLabel="Accuracy"
                title="Quality against tokens" subtitle="95% Wilson intervals on accuracy" legend={CONFIG_LEGEND}
                summary={r.variants.map((v) => `${v.variant_id}: ${fmt(v.accuracy_valid_gold)} at ${Math.round(v.tokens_mean)} tokens`).join('; ')} />
            </div>
            <div className="cw-card">
              <Frontier points={frontierPoints(r, 'e2e_latency_p50_s')} xLabel="Median summed agent-call time (s)" yLabel="Accuracy"
                xFmt={(v) => `${Math.round(v)}`} title="Quality against latency" subtitle="Parallel checks counted serially (an upper bound on wall clock)" legend={CONFIG_LEGEND}
                summary={r.variants.map((v) => `${v.variant_id}: ${fmt(v.accuracy_valid_gold)} at ${fmt(v.e2e_latency_p50_s, 0)} s`).join('; ')} />
            </div>
          </div>
          <div className="cw-card">
            <SmallMultiples metrics={overheadMetrics(r)} title="Governance overhead per case"
              subtitle="Model calls, tokens and governance-only latency (everything except the shared research and diagnosis steps)"
              summary="Overhead per configuration" />
          </div>
          <div className="cw-cols-32">
            <div className="cw-card">
              <h3>Summed agent-call time per case (s)</h3>
              <div style={{ height: 280 }}>
                <Bar options={barOptions('Summed agent-call time (s)')} data={{ labels, datasets: [
                  { label: 'Median', data: r.variants.map((v) => v.e2e_latency_p50_s), backgroundColor: CHART.primary },
                  { label: '95th percentile', data: r.variants.map((v) => v.e2e_latency_p95_s), backgroundColor: CHART.secondary },
                ] }} />
              </div>
            </div>
            <div className="cw-card">
              <h3>Tokens and cost per case</h3>
              <Table rows={r.variants} cols={[
                ['variant_id', 'Variant'], ['tokens_mean', 'Tokens', 0], ['cost_mean_usd', 'Cost (USD)', 5],
              ]} />
            </div>
          </div>
          <div className="cw-card">
            <h3>Where the time goes (per agent)</h3>
            <Table rows={r.latency_by_agent} cols={[
              ['agent', 'Agent'], ['calls', 'Calls', 0], ['mean_s', 'Mean (s)', 1], ['p95_s', 'p95 (s)', 1], ['max_s', 'Max (s)', 1],
              ['mean_share_of_run', 'Share of run', 2, (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)], ['mean_tokens', 'Tokens', 0],
            ]} />
            <p className="cw-muted" style={{ marginTop: 8 }}>{r.measurement_validity.latency_note} Variants ran concurrently against one endpoint, so latency includes contention.</p>
          </div>
        </>
      )}

      {tab === 'signals' && (
        <>
          <div className="cw-card">
            <h3>How well each governance signal detects a wrong diagnosis (AUROC, 0.5 = chance)</h3>
            <div style={{ height: 280 }}>
              <Bar options={barOptions('AUROC', 1, { autoSkip: false })} data={{
                labels: signals.map((s) => `${s.signal} · ${s.variant_id}`),
                datasets: [{ label: 'AUROC', data: signals.map((s) => s.auroc), backgroundColor: signals.map((s) => ((s.auroc ?? 0) >= 0.65 ? CHART.primary : CHART.secondary)) }],
              }} />
            </div>
          </div>
          <div className="cw-card">
            <Table rows={signals} cols={[
              ['signal', 'Signal'], ['variant_id', 'Variant'], ['n', 'n', 0],
              ['fire_rate', 'Fires on', 2, (v) => (v == null ? '—' : `${Math.round(v * 100)}%`)], ['sensitivity', 'Sensitivity'],
              ['false_positive_rate', 'False-positive rate'], ['precision', 'Precision'], ['auroc', 'AUROC'],
            ]} />
          </div>
        </>
      )}

      {tab === 'closed' && r.revision_by_variant?.length > 0 && (
        <>
          <div className="cw-card">
            <DivergingBars rows={revisionRows(r)} title="Revision impact"
              subtitle="Within each closed-loop run: answers the revision made right versus answers it made wrong (exact sign test, unadjusted)"
              summary={revisionRows(r).map((x) => `${x.id}: fixed ${x.fixed}, broken ${x.broken}`).join('; ')} />
          </div>
          <div className="cw-card">
            <h3>What revision did, within each run <span className="cw-muted">· first answer vs. revised answer, same question</span></h3>
            <Table rows={r.revision_by_variant} cols={[
              ['variant_id', 'Configuration', 0, (v) => VARIANT_LABELS[v] || v], ['revision_rate', 'Revised', 0, pctOf],
              ['revised_runs_scored', 'Scored revisions', 0], ['within_run_fixed', 'Fixed', 0], ['within_run_broken', 'Broken', 0],
              ['sign_test_p', 'Sign test p (unadjusted)', 0, pval],
            ]} />
            <p className="cw-muted" style={{ marginBottom: 0 }}>Fixed: the first answer was wrong and the revision made it right. Broken: the reverse. Exact two-sided sign test on fixed vs. broken, not corrected for multiple comparisons.</p>
          </div>
          {r.closed_loop_effect?.length > 0 && (
            <div className="cw-card">
              <h3>Closed vs. open loop <span className="cw-muted">· same questions</span></h3>
              <Table rows={r.closed_loop_effect} cols={[
                ['comparison', 'Comparison'], ['n_pairs', 'n', 0], ['accuracy_open', 'Open', 3], ['accuracy_closed', 'Closed', 3],
                ['accuracy_diff', 'Difference', 3], ['accuracy_diff_ci95_low', '95% CI low', 3], ['accuracy_diff_ci95_high', '95% CI high', 3],
                ['mcnemar_exact_p', 'McNemar p', 0, pval], ['first_diagnosis_differs', 'First diagnosis differs', 0],
              ]} />
              <p className="cw-muted" style={{ marginBottom: 0 }}>"First diagnosis differs" counts questions where the closed-loop run did not start from the open-loop answer; above zero, the comparison mixes revision with resampling.</p>
            </div>
          )}
          {r.resampling_stability?.some((x) => x.answer_agreement < 1) && (
            <div className="cw-card">
              <h3>Run-to-run stability <span className="cw-muted">· regenerated first diagnosis vs. V1</span></h3>
              <Table rows={r.resampling_stability} cols={[
                ['resample', 'Resample'], ['n_pairs', 'n', 0], ['answer_agreement', 'Same answer', 0, pctOf],
                ['correctness_flips', 'Correctness flips', 0], ['accuracy_v1', 'V1 accuracy', 3], ['accuracy_resample', 'Resample accuracy', 3],
              ]} />
            </div>
          )}
        </>
      )}

      {tab === 'stats' && (
        <>
          <div className="cw-card">
            <ForestPlot rows={forestRows(r)} xLabel="Accuracy difference vs G0 (percentage points)" title="Paired accuracy differences"
              subtitle="Same cases, bootstrap 95% interval. Blue: the uncorrected interval excludes zero, which is not significance after correction (see Holm p). p: exact McNemar; Holm p: corrected over all paired tests in the report"
              summary={forestRows(r).map((x) => `${x.id} ${(x.diff * 100).toFixed(1)} points`).join('; ')} />
          </div>
          {r.accuracy_tests?.length > 0 && (
            <div className="cw-card">
              <h3>Accuracy vs. V1 on the same cases <span className="cw-muted">· exact McNemar, bootstrap 95% CI, Holm-adjusted p</span></h3>
              <Table rows={r.accuracy_tests} cols={[
                ['comparison', 'Comparison'], ['n_pairs', 'n', 0], ['accuracy_v1', 'V1', 3], ['accuracy_variant', 'Variant', 3],
                ['accuracy_diff', 'Difference', 3], ['accuracy_diff_ci95_low', 'CI low', 3], ['accuracy_diff_ci95_high', 'CI high', 3],
                ['mcnemar_exact_p', 'p', 0, pval], ['mcnemar_exact_p_holm', 'Holm p', 0, pval],
              ]} />
            </div>
          )}
          <div className="cw-card">
            <h3>Paired differences vs. V1 <span className="cw-muted">· bootstrap 95% CI, Wilcoxon signed-rank, Holm-adjusted p</span></h3>
            <Table rows={r.paired_tests} cols={[
              ['metric', 'Metric'], ['comparison', 'Comparison'], ['n_pairs', 'n', 0], ['mean_diff', 'Mean diff'],
              ['ci95_low', 'CI low'], ['ci95_high', 'CI high'], ['wilcoxon_p', 'p', 0, pval], ['wilcoxon_p_holm', 'Holm p', 0, pval],
            ]} />
            {r.multiple_comparisons && (
              <p className="cw-muted" style={{ marginBottom: 0 }}>
                Holm–Bonferroni over {r.multiple_comparisons.family_size} paired tests: {r.multiple_comparisons.significant_raw} significant before
                correction, {r.multiple_comparisons.significant_after_holm} after.
              </p>
            )}
          </div>
        </>
      )}
      {tab === 'findings' && <FindingsPanel report={r} />}
    </div>
  );
}
