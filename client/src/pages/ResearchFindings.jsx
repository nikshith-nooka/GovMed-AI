import React, { useEffect, useState } from 'react';
import { AlertTriangle, FlaskConical, Loader2 } from 'lucide-react';
import './clinical.css';

const fmt = (v, d = 3) => (v == null ? '—' : typeof v === 'number' ? v.toFixed(d) : String(v));

function Table({ rows, cols }) {
  if (!rows?.length) return <p className="cw-muted">No data.</p>;
  return (
    <div className="cw-table-wrap">
      <table className="cw-table">
        <thead><tr>{cols.map(([key, label]) => <th key={key}>{label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{cols.map(([key, , digits]) => <td key={key} className="cw-num">{typeof r[key] === 'number' ? fmt(r[key], digits ?? 3) : fmt(r[key])}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AurocBar({ value }) {
  if (value == null) return '—';
  const left = Math.min(value, 0.5) * 100;
  const width = Math.abs(value - 0.5) * 100;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ position: 'relative', width: 120, height: 8, background: 'var(--border-color)', borderRadius: 9999 }}>
        <div style={{ position: 'absolute', left: '50%', top: -3, width: 1, height: 14, background: 'var(--text-muted)' }} />
        <div style={{ position: 'absolute', left: `${value >= 0.5 ? 50 : left}%`, width: `${width}%`, height: 8, borderRadius: 9999, background: value >= 0.6 ? 'var(--accent-green)' : '#EA580C' }} />
      </div>
      <span className="cw-num">{value.toFixed(3)}</span>
    </div>
  );
}

export default function ResearchFindings() {
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/research/findings')
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail || 'Report unavailable');
        setReport(body);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <div className="cw-page"><div className="cw-banner info"><FlaskConical size={18} /><div><strong>No analysis yet</strong>{error}</div></div></div>;
  }
  if (!report) return <div className="cw-page cw-empty"><Loader2 className="spin" /> Loading analysis…</div>;

  const m = report.measurement_validity;
  const paired = report.paired_tests.filter((t) => ['accuracy', 'detector_neutral_quality', 'e2e_latency_s'].includes(t.metric));

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Research Findings</h2>
          <p className="cw-sub">Re-analysis of {report.n_runs_analyzed} stored runs over {report.n_cases} cases ({report.models.join(', ')}) using only measured quantities. Generated {new Date(report.generated_at * 1000).toLocaleString()}.</p>
        </div>
      </div>

      {report.integrity.notes.length > 0 && (
        <div className="cw-banner high" style={{ marginBottom: 14 }}>
          <AlertTriangle size={18} />
          <div><strong>Data integrity</strong><ul>{report.integrity.notes.map((n) => <li key={n}>{n}</li>)}</ul></div>
        </div>
      )}

      <div className="cw-card">
        <h3>Headline findings</h3>
        {report.headline_findings.map((f, i) => (
          <div key={i} className="cw-finding"><span className="cw-num cw-muted">{i + 1}.</span><span>{f}</span></div>
        ))}
      </div>

      <div className="cw-two" style={{ marginTop: 14 }}>
        <div className="cw-card">
          <h3>Measurement validity</h3>
          <div className="cw-checks">
            <div><span>Scorable cases (real diagnosis labels)</span><strong className="cw-num">{m.cases_with_valid_gold} / {m.cases_total}</strong></div>
            <div><span>Runs with unparsed diagnosis</span><strong className="cw-num">{m.runs_with_unparsed_diagnosis}</strong></div>
            <div><span>Accuracy: reported vs. corrected</span><strong className="cw-num">{fmt(m.reported_accuracy_mean)} → {fmt(m.corrected_accuracy_mean_all_cases)}</strong></div>
            <div><span>Accuracy on scorable cases</span><strong className="cw-num">{fmt(m.corrected_accuracy_mean_valid_gold)}</strong></div>
            {Object.entries(m.parse_failure_rate_by_agent).map(([agent, v]) => (
              <div key={agent}><span>JSON parse failures: {agent}</span><strong className="cw-num">{v.failed}/{v.total} ({Math.round(v.rate * 100)}%)</strong></div>
            ))}
          </div>
          <p className="cw-muted" style={{ marginTop: 10 }}>{m.latency_note}</p>
        </div>
        <div className="cw-card" style={{ marginTop: 0 }}>
          <h3>Clinician validation</h3>
          {report.clinician_validation.n_reviews ? (
            <div className="cw-checks">
              <div><span>Reviews / reviewers</span><strong className="cw-num">{report.clinician_validation.n_reviews} / {report.clinician_validation.n_reviewers}</strong></div>
              <div><span>Alert precision (clinician-rated)</span><strong className="cw-num">{fmt(report.clinician_validation.alert_precision_by_clinicians)}</strong></div>
              <div><span>Auto-scorer vs. clinician agreement</span><strong className="cw-num">{fmt(report.clinician_validation.auto_vs_clinician_agreement)}</strong></div>
              <div><span>Cohen's kappa</span><strong className="cw-num">{fmt(report.clinician_validation.auto_vs_clinician_kappa)}</strong></div>
            </div>
          ) : <p className="cw-muted">{report.clinician_validation.status}</p>}
          <h3 style={{ marginTop: 16 }}>Limitations</h3>
          <ul className="cw-list">{report.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
        </div>
      </div>

      <div className="cw-card">
        <h3>Variants (measured)</h3>
        <Table rows={report.variants} cols={[
          ['variant_id', 'Variant'], ['accuracy_valid_gold', 'Accuracy*'], ['detector_neutral_quality', 'Detector-neutral quality'],
          ['reported_quality', 'Reported quality'], ['tokens_mean', 'Tokens', 0], ['e2e_latency_p50_s', 'p50 s', 1],
          ['e2e_latency_p95_s', 'p95 s', 1], ['diagnosis_changed_vs_v1_pct', 'Dx changed vs V1 %', 1]]} />
        <p className="cw-muted" style={{ marginTop: 8 }}>*On scorable cases only. Reported quality penalizes each variant for its own detectors' flags; detector-neutral quality does not.</p>
      </div>

      <div className="cw-card">
        <h3>Paired comparisons vs. V1 (same cases)</h3>
        <Table rows={paired} cols={[['metric', 'Metric'], ['comparison', 'Comparison'], ['n_pairs', 'n', 0], ['mean_diff', 'Mean diff'],
          ['ci95_low', 'CI low'], ['ci95_high', 'CI high'], ['wilcoxon_p', 'Wilcoxon p', 4]]} />
      </div>

      <div className="cw-card">
        <h3>Do governance signals detect wrong diagnoses?</h3>
        <div className="cw-table-wrap">
          <table className="cw-table">
            <thead><tr><th>Signal</th><th>Variant</th><th>Fires on</th><th>Sensitivity</th><th>False-positive rate</th><th>Precision</th><th>AUROC (0.5 = chance)</th></tr></thead>
            <tbody>
              {report.alert_discrimination.map((a, i) => (
                <tr key={i}>
                  <td>{a.signal}</td><td>{a.variant_id}</td><td className="cw-num">{Math.round(a.fire_rate * 100)}%</td>
                  <td className="cw-num">{fmt(a.sensitivity)}</td><td className="cw-num">{fmt(a.false_positive_rate)}</td>
                  <td className="cw-num">{fmt(a.precision)}</td><td><AurocBar value={a.auroc} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="cw-two" style={{ marginTop: 14 }}>
        <div className="cw-card">
          <h3>Latency by agent</h3>
          <Table rows={report.latency_by_agent} cols={[['agent', 'Agent'], ['calls', 'Calls', 0], ['mean_s', 'Mean s', 1], ['p95_s', 'p95 s', 1], ['max_s', 'Max s', 1]]} />
        </div>
        <div className="cw-card" style={{ marginTop: 0 }}>
          <h3>Calibration of model-reported likelihood (V1)</h3>
          <p className="cw-muted" style={{ marginTop: 0 }}>ECE {fmt(report.calibration.ece)} · Brier {fmt(report.calibration.brier)} · n = {report.calibration.n}</p>
          <Table rows={report.calibration.bins} cols={[['bin', 'Stated'], ['n', 'n', 0], ['mean_confidence', 'Mean stated'], ['observed_accuracy', 'Observed']]} />
        </div>
      </div>

      <div className="cw-card">
        <h3>By dataset (V1)</h3>
        <Table rows={report.strata.dataset} cols={[['dataset', 'Dataset'], ['cases', 'Cases', 0], ['cases_valid_gold', 'Scorable', 0],
          ['accuracy_valid_gold', 'Accuracy'], ['diagnosis_parse_failure_rate', 'Parse failure rate']]} />
      </div>
    </div>
  );
}
