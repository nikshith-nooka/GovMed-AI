import React, { useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js';
import { FlaskConical, Loader2 } from 'lucide-react';
import { VARIANT_LABELS, fmt, useApi } from '../lib/api';
import './clinical.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

const TABS = [
  ['variants', 'Variant comparison'],
  ['cost', 'Cost & latency'],
  ['signals', 'Governance signals'],
  ['stats', 'Paired statistics'],
];

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

const barOptions = (yTitle, max) => ({
  maintainAspectRatio: false,
  plugins: { legend: { position: 'bottom' } },
  scales: { y: { beginAtZero: true, ...(max ? { max } : {}), title: { display: true, text: yTitle } } },
});

export default function ResultsComparison() {
  const [tab, setTab] = useState('variants');
  const { data: r, error, loading } = useApi('/api/research/findings');

  if (loading) return <div className="cw-page cw-empty"><Loader2 className="spin" /> Loading…</div>;
  if (error) return <div className="cw-page"><div className="cw-banner info"><FlaskConical size={18} /><div><strong>No analysis yet</strong>{error}</div></div></div>;

  const labels = r.variants.map((v) => VARIANT_LABELS[v.variant_id] || v.variant_id);
  const signals = r.alert_discrimination;

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Benchmark Analytics</h2>
          <p className="cw-sub">{r.n_runs_analyzed} runs, {r.n_cases} cases, {r.models.join(', ')}. Accuracy is computed on the {r.measurement_validity.cases_with_valid_gold} cases with a real diagnosis label.</p>
        </div>
      </div>
      <div className="cw-tabs cw-seg" role="tablist" style={{ display: 'inline-flex' }}>
        {TABS.map(([id, label]) => <button key={id} role="tab" aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}
      </div>

      {tab === 'variants' && (
        <>
          <div className="cw-card">
            <h3>Quality by variant</h3>
            <div style={{ height: 300 }}>
              <Bar options={barOptions('Score (0-1)', 1)} data={{ labels, datasets: [
                { label: 'Accuracy (scorable cases)', data: r.variants.map((v) => v.accuracy_valid_gold), backgroundColor: '#E07A5F' },
                { label: 'Detector-neutral quality', data: r.variants.map((v) => v.detector_neutral_quality), backgroundColor: '#2D6A4F' },
                { label: 'Reported quality', data: r.variants.map((v) => v.reported_quality), backgroundColor: '#CBD5E1' },
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
          <div className="cw-cols-32">
            <div className="cw-card">
              <h3>End-to-end latency (seconds)</h3>
              <div style={{ height: 280 }}>
                <Bar options={barOptions('Seconds')} data={{ labels, datasets: [
                  { label: 'Median', data: r.variants.map((v) => v.e2e_latency_p50_s), backgroundColor: '#2D6A4F' },
                  { label: '95th percentile', data: r.variants.map((v) => v.e2e_latency_p95_s), backgroundColor: '#E07A5F' },
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
              <Bar options={barOptions('AUROC', 1)} data={{
                labels: signals.map((s) => `${s.signal} · ${s.variant_id}`),
                datasets: [{ label: 'AUROC', data: signals.map((s) => s.auroc), backgroundColor: signals.map((s) => ((s.auroc ?? 0) >= 0.65 ? '#2D6A4F' : '#E07A5F')) }],
              }} />
            </div>
          </div>
          <div className="cw-card">
            <Table rows={signals} cols={[
              ['signal', 'Signal'], ['variant_id', 'Variant'], ['n', 'n', 0],
              ['fire_rate', 'Fires on', 2, (v) => `${Math.round(v * 100)}%`], ['sensitivity', 'Sensitivity'],
              ['false_positive_rate', 'False-positive rate'], ['precision', 'Precision'], ['auroc', 'AUROC'],
            ]} />
          </div>
        </>
      )}

      {tab === 'stats' && (
        <div className="cw-card">
          <h3>Paired differences vs. V1 on the same cases (bootstrap 95% CI, Wilcoxon signed-rank)</h3>
          <Table rows={r.paired_tests} cols={[
            ['metric', 'Metric'], ['comparison', 'Comparison'], ['n_pairs', 'n', 0], ['mean_diff', 'Mean diff'],
            ['ci95_low', 'CI low'], ['ci95_high', 'CI high'], ['wilcoxon_p', 'p', 4],
          ]} />
        </div>
      )}
    </div>
  );
}
