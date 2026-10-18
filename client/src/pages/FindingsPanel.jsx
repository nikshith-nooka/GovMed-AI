import React from 'react';
import { AlertTriangle } from 'lucide-react';
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

/**
 * Findings & validity: the parts of the analysis report no other view shows (headline findings, integrity audit,
 * measurement validity, clinician validation, limitations, calibration, per-agent latency, strata). Formerly the
 * standalone Research Findings page; variant, paired-test and signal tables now live only in Benchmark Results.
 */
export default function FindingsPanel({ report }) {
  const m = report.measurement_validity;

  return (
    <div>
      <p className="cw-muted" style={{ marginTop: 0 }}>Re-analysis of {report.n_runs_analyzed} stored runs over {report.n_cases} cases ({(report.models || []).join(', ')}) using only measured quantities. Generated {new Date(report.generated_at * 1000).toLocaleString()}.</p>

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
