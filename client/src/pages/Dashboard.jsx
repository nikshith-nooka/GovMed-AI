import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, BarElement, Tooltip, Legend } from 'chart.js';
import { AlertTriangle, ArrowRight, ClipboardCheck, FlaskConical, HeartPulse, Loader2 } from 'lucide-react';
import { EXAMPLE_CASES, VARIANT_LABELS, fmt, useApi } from '../lib/api';
import './clinical.css';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

function Kpi({ label, value, note }) {
  return (
    <div className="cw-card">
      <div className="cw-muted" style={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.04em' }}>{label}</div>
      <div className="cw-num" style={{ fontSize: '1.6rem', fontWeight: 800, margin: '4px 0' }}>{value}</div>
      <div className="cw-muted">{note}</div>
    </div>
  );
}

export default function Dashboard({ setCurrentPage, stats, openInWorkspace }) {
  const { data: report, error, loading } = useApi('/api/research/findings');
  const reviews = useApi('/api/reviews/summary');

  const variants = report?.variants || [];
  const v1 = variants.find((v) => v.variant_id === 'V1');
  const v5 = variants.find((v) => v.variant_id === 'V5');
  const m = report?.measurement_validity;

  const chart = {
    labels: variants.map((v) => VARIANT_LABELS[v.variant_id] || v.variant_id),
    datasets: [
      { label: 'Reported quality (penalizes own detectors)', data: variants.map((v) => v.reported_quality), backgroundColor: '#CBD5E1' },
      { label: 'Detector-neutral quality', data: variants.map((v) => v.detector_neutral_quality), backgroundColor: '#2D6A4F' },
      { label: 'Accuracy (scorable cases)', data: variants.map((v) => v.accuracy_valid_gold), backgroundColor: '#E07A5F' },
    ],
  };

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">GovBench-Clinical</h2>
          <p className="cw-sub">
            A benchmark and decision-support workbench for multi-agent clinical AI. It measures what governance layers
            (grounding verifier, safety validator, simulated attending review) actually change, and gives clinicians an
            interface that shows what was and was not checked.
          </p>
        </div>
      </div>

      <div className="cw-cols-3">
        <button className="cw-card cw-tile" onClick={() => setCurrentPage('clinician')}>
          <HeartPulse size={20} /> <strong>Clinician Workspace</strong>
          <p className="cw-muted" style={{ margin: '6px 0 0' }}>Analyze a patient with a live model, for physicians and clinical assistants.</p>
        </button>
        <button className="cw-card cw-tile" onClick={() => setCurrentPage('review')}>
          <ClipboardCheck size={20} /> <strong>Clinician Review</strong>
          <p className="cw-muted" style={{ margin: '6px 0 0' }}>
            Blinded rating of AI outputs.{reviews.data ? ` ${reviews.data.n_reviews} reviews from ${reviews.data.n_reviewers} reviewer(s) so far.` : ''}
          </p>
        </button>
        <button className="cw-card cw-tile" onClick={() => setCurrentPage('findings')}>
          <FlaskConical size={20} /> <strong>Research Findings</strong>
          <p className="cw-muted" style={{ margin: '6px 0 0' }}>Measured results, integrity audit and limitations.</p>
        </button>
      </div>

      {loading && <div className="cw-card cw-empty" style={{ marginTop: 14 }}><Loader2 className="spin" /> Loading measured results…</div>}
      {error && <div className="cw-banner info" style={{ marginTop: 14 }}><FlaskConical size={18} /><div><strong>No analysis yet</strong>{error}</div></div>}

      {report && (
        <>
          {report.integrity.notes.length > 0 && (
            <div className="cw-banner high" style={{ marginTop: 14 }}>
              <AlertTriangle size={18} />
              <div><strong>Some stored metrics are not measurements</strong>They are excluded here. See Research Findings for details.</div>
            </div>
          )}
          <div className="cw-cols-4" style={{ marginTop: 14 }}>
            <Kpi label="Runs analyzed" value={report.n_runs_analyzed} note={`${report.n_cases} cases × 5 variants · ${stats?.total_runs ?? '—'} rows stored`} />
            <Kpi label="Scorable cases" value={`${m.cases_with_valid_gold}/${m.cases_total}`} note="The rest have templated gold labels" />
            <Kpi label="Baseline accuracy" value={fmt(v1?.accuracy_valid_gold, 3)} note={`Reported ${fmt(m.reported_accuracy_mean, 3)} before scoring fixes`} />
            <Kpi label="Median latency" value={`${fmt(v1?.e2e_latency_p50_s, 0)}–${fmt(v5?.e2e_latency_p50_s, 0)} s`} note="V1 to V5, end to end, benchmark model" />
          </div>

          <div className="cw-cols-32" style={{ marginTop: 14 }}>
            <div className="cw-card">
              <h3>Quality by variant</h3>
              <div style={{ height: 280 }}>
                <Bar data={chart} options={{ maintainAspectRatio: false, scales: { y: { min: 0, max: 1 } }, plugins: { legend: { position: 'bottom' } } }} />
              </div>
              <button className="cw-btn ghost small" style={{ marginTop: 10 }} onClick={() => setCurrentPage('results')}>Open Benchmark Analytics <ArrowRight size={14} /></button>
            </div>
            <div className="cw-card">
              <h3>Key findings</h3>
              {report.headline_findings.slice(0, 5).map((f, i) => (
                <div key={i} className="cw-finding"><span className="cw-num cw-muted">{i + 1}.</span><span>{f}</span></div>
              ))}
              <button className="cw-btn ghost small" style={{ marginTop: 10 }} onClick={() => setCurrentPage('findings')}>All findings <ArrowRight size={14} /></button>
            </div>
          </div>
        </>
      )}

      <div className="cw-card" style={{ marginTop: 14 }}>
        <h3>Try an example patient in the Clinician Workspace</h3>
        <div className="cw-cols-4">
          {EXAMPLE_CASES.map((ex) => (
            <button key={ex.id} className="cw-card cw-tile" onClick={() => openInWorkspace(ex)}>
              <strong>{ex.label}</strong>
              <div className="cw-muted" style={{ margin: '4px 0' }}>{ex.tag}</div>
              <div style={{ fontSize: '0.78rem' }}>{ex.chief_complaint}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
