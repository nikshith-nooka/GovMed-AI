import React from 'react';
import { AlertTriangle, ArrowRight, FlaskConical, Loader2 } from 'lucide-react';
import { findingsPath, fmt, useApi, useExperiment } from '../lib/api';
import { DotPlotCI, Frontier, LegendItem } from '../components/charts';
import { accuracyRows, frontierPoints, scorableCases } from '../lib/research';
import './clinical.css';

function Stat({ label, value, note }) {
  return (
    <div className="cw-stat">
      <div className="cw-section-label" style={{ margin: 0 }}>{label}</div>
      <div className="cw-stat-value cw-num">{value}</div>
      <div className="cw-muted">{note}</div>
    </div>
  );
}

const range = (vals, f) => {
  const v = vals.filter((x) => x != null);
  return v.length ? `${f(Math.min(...v))}–${f(Math.max(...v))}` : '—';
};

export const CONFIG_LEGEND = (
  <>
    <LegendItem shape="square" color="var(--chart-neutral)">Open loop / no checks</LegendItem>
    <LegendItem shape="circle" color="var(--chart-primary)">Closed loop (revision)</LegendItem>
  </>
);

export default function Dashboard({ setCurrentPage }) {
  const experiment = useExperiment();
  const { data: report, error, loading } = useApi(findingsPath(experiment));
  const { data: listing } = useApi('/api/research/experiments');
  const meta = listing?.experiments?.find((e) => e.key === experiment);

  const variants = report?.variants || [];
  const v1 = variants.find((v) => v.variant_id === 'V1');
  const m = report?.measurement_validity;
  const n = scorableCases(report);
  const rows = report ? accuracyRows(report) : [];
  const g0 = rows.find((r) => r.id === 'V1');
  const exact = m && m.cases_with_answer_key === m.cases_total;

  return (
    <div className="cw-page">
      <header className="cw-header">
        <div>
          <div className="cw-eyebrow">
            <FlaskConical size={14} aria-hidden="true" /> {meta ? meta.label : 'Selected experiment'}
            {meta && <span className={`cw-pill ${meta.status.startsWith('superseded') ? 'pill-warning' : 'pill-accent'}`}>{meta.status}</span>}
          </div>
          <h2 className="cw-title">Overview</h2>
          <p className="cw-sub">
            {report
              ? `${report.n_runs_analyzed.toLocaleString()} analysed runs over ${report.n_cases} cases and ${variants.length} governance configurations, ${(report.models || []).join(', ')}. ${exact ? 'Answers are scored exactly against the answer key.' : `Accuracy uses the ${m.cases_with_valid_gold} cases with a real diagnosis label.`}`
              : 'How much each governance layer changes diagnostic quality, and what it costs in tokens and time.'}
          </p>
        </div>
      </header>

      {loading && <div className="cw-card cw-empty"><Loader2 className="spin" aria-hidden="true" /> Loading measured results…</div>}
      {error && <div className="cw-banner info" role="alert"><FlaskConical size={18} aria-hidden="true" /><div><strong>No analysis for this experiment</strong>{error}</div></div>}

      {report && (
        <>
          {report.integrity?.notes?.length > 0 && (
            <div className="cw-banner high" style={{ marginBottom: 16 }}>
              <AlertTriangle size={18} aria-hidden="true" />
              <div><strong>Some stored metrics are not measurements</strong>They are excluded from every figure here. Details are under Benchmark Results › Findings &amp; validity.</div>
            </div>
          )}

          <section className="cw-card cw-stats" aria-label="Summary">
            <Stat label="Baseline accuracy (G0)" value={fmt(v1?.accuracy_valid_gold, 3)}
              note={g0?.lo != null ? `95% CI ${fmt(g0.lo, 3)}–${fmt(g0.hi, 3)} · n = ${n}` : `n = ${n ?? '—'}`} />
            <Stat label="Accuracy across configurations" value={range(variants.map((v) => v.accuracy_valid_gold), (v) => v.toFixed(3))}
              note="See the paired tests before reading differences as effects" />
            <Stat label="Tokens per case" value={range(variants.map((v) => v.tokens_mean), (v) => Math.round(v).toLocaleString())}
              note="Mean over all model calls of a run" />
            <Stat label="Summed agent-call time" value={`${range(variants.map((v) => v.e2e_latency_p50_s), (v) => Math.round(v))} s`}
              note="Median per case; parallel checks counted serially" />
          </section>

          <div className="cw-two" style={{ marginTop: 16 }}>
            <div className="cw-card">
              <DotPlotCI rows={rows} reference={g0?.value} xLabel="Accuracy (axis fitted to data)"
                title="Diagnostic accuracy by configuration"
                subtitle="Point estimate with 95% Wilson interval; dashed line = G0 baseline"
                legend={CONFIG_LEGEND}
                summary={rows.map((r) => `${r.id} ${fmt(r.value, 3)}`).join(', ')} />
            </div>
            <div className="cw-card">
              <Frontier points={frontierPoints(report, 'tokens_mean')} xLabel="Mean tokens per case" yLabel="Accuracy"
                title="Quality against cost" subtitle="Up and to the left is better"
                legend={CONFIG_LEGEND}
                summary={variants.map((v) => `${v.variant_id}: accuracy ${fmt(v.accuracy_valid_gold, 3)} at ${Math.round(v.tokens_mean)} tokens`).join('; ')} />
            </div>
          </div>

          <section className="cw-card" style={{ marginTop: 16 }} aria-labelledby="findings-head">
            <h3 id="findings-head">What the analysis found</h3>
            {report.headline_findings.slice(0, 4).map((f, i) => (
              <div key={i} className="cw-finding"><span className="cw-num cw-muted">{i + 1}.</span><span>{f}</span></div>
            ))}
            <div className="cw-toolbar" style={{ marginTop: 12 }}>
              <button className="cw-btn ghost small" onClick={() => setCurrentPage('results')}>Benchmark Results <ArrowRight size={14} aria-hidden="true" /></button>
              <button className="cw-btn ghost small" onClick={() => setCurrentPage('results', 'findings')}>All findings &amp; limitations <ArrowRight size={14} aria-hidden="true" /></button>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
