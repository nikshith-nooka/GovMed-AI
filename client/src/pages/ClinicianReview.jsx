import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ClipboardCheck, Loader2 } from 'lucide-react';
import './clinical.css';

const ROLES = [
  ['physician', 'Physician'], ['resident', 'Resident'], ['nurse', 'Nurse'],
  ['physician_assistant', 'Physician assistant'], ['pharmacist', 'Pharmacist'], ['other', 'Other'],
];
const VERDICTS = [['correct', 'Correct'], ['acceptable', 'Acceptable alternative'], ['incorrect', 'Incorrect'], ['unsure', 'Unsure']];

function readStored(key) {
  try { return window.localStorage.getItem(key) || ''; } catch { return ''; }
}
function store(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* storage unavailable */ }
}

function RateButtons({ options, value, onChange }) {
  return (
    <div className="cw-rate">
      {options.map(([id, label]) => (
        <button key={id} type="button" aria-pressed={value === id} onClick={() => onChange(id)}>{label}</button>
      ))}
    </div>
  );
}

export default function ClinicianReview() {
  const [reviewerId, setReviewerId] = useState(() => readStored('govbench.reviewer'));
  const [role, setRole] = useState(() => readStored('govbench.reviewerRole') || 'physician');
  const [queue, setQueue] = useState(null);
  const [index, setIndex] = useState(0);
  const [form, setForm] = useState({ verdict: '', quality: 0, alerts: {}, missed: '', comments: '' });
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const loadSummary = () => fetch('/api/reviews/summary').then((r) => r.json()).then(setSummary).catch(() => {});
  useEffect(() => { loadSummary(); }, []);

  const loadQueue = async () => {
    if (!reviewerId.trim()) return;
    store('govbench.reviewer', reviewerId.trim());
    store('govbench.reviewerRole', role);
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/reviews/queue?reviewer_id=${encodeURIComponent(reviewerId.trim())}&limit=10`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || 'Could not load cases');
      setQueue(body);
      setIndex(0);
      setForm({ verdict: '', quality: 0, alerts: {}, missed: '', comments: '' });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const item = queue?.items?.[index];
  const complete = form.verdict && form.quality > 0;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/reviews', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id: item.run_id,
          case_id: item.case_id,
          reviewer_id: reviewerId.trim(),
          reviewer_role: role,
          diagnosis_verdict: form.verdict,
          quality_rating: form.quality,
          alert_ratings: Object.entries(form.alerts).map(([i, verdict]) => ({ index: Number(i), verdict })),
          missed_hazards: form.missed,
          comments: form.comments,
        }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      setForm({ verdict: '', quality: 0, alerts: {}, missed: '', comments: '' });
      loadSummary();
      if (index + 1 < queue.items.length) setIndex(index + 1);
      else await loadQueue();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Clinician Review</h2>
          <p className="cw-sub">Rate AI outputs from the benchmark. Your ratings measure how often the AI's alerts are real and whether the automatic scorer agrees with clinicians, which is the validation the study still needs. Which governance level produced each output is hidden.</p>
        </div>
      </div>

      <div className="cw-grid">
        <div>
          <div className="cw-card">
            <h3>Reviewer</h3>
            <div className="cw-field">
              <label className="cw-label" htmlFor="rv-id">Reviewer ID (initials or pseudonym, no patient data)</label>
              <input id="rv-id" className="cw-input" value={reviewerId} maxLength={80} onChange={(e) => setReviewerId(e.target.value)} />
            </div>
            <div className="cw-field">
              <label className="cw-label" htmlFor="rv-role">Role</label>
              <select id="rv-role" className="cw-select" value={role} onChange={(e) => setRole(e.target.value)}>
                {ROLES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
              </select>
            </div>
            <button className="cw-btn full" disabled={!reviewerId.trim() || busy} onClick={loadQueue}>
              {busy && !queue ? <Loader2 size={16} className="spin" /> : <ClipboardCheck size={16} />} Start reviewing
            </button>
          </div>
          <div className="cw-card">
            <h3>Study progress</h3>
            {summary && summary.n_reviews > 0 ? (
              <div className="cw-checks">
                <div><span>Reviews collected</span><strong className="cw-num">{summary.n_reviews}</strong></div>
                <div><span>Reviewers</span><strong className="cw-num">{summary.n_reviewers}</strong></div>
                <div><span>Alerts rated</span><strong className="cw-num">{summary.n_alerts_rated}</strong></div>
                <div><span>Alert precision (rated valid)</span><strong className="cw-num">{summary.alert_precision == null ? '—' : `${Math.round(summary.alert_precision * 100)}%`}</strong></div>
                <div><span>Mean quality rating</span><strong className="cw-num">{summary.mean_quality_rating} / 5</strong></div>
              </div>
            ) : <p className="cw-muted">No reviews yet. Aim for at least 3 reviewers on the same 50 cases so agreement can be measured.</p>}
          </div>
        </div>

        <div className="cw-stack">
          {error && <div className="cw-banner error"><AlertTriangle size={18} /><div><strong>Problem</strong>{error}</div></div>}
          {!queue && <div className="cw-card cw-empty">Enter a reviewer ID to get your case queue.</div>}
          {queue && !item && <div className="cw-banner standard"><CheckCircle2 size={18} /><div><strong>All done</strong>You have reviewed every available output. Thank you.</div></div>}
          {item && (
            <>
              <div className="cw-card">
                <h3>Case {index + 1} of {queue.items.length} · {queue.remaining} remaining overall</h3>
                <div className="cw-case-text">{item.case_text}</div>
              </div>
              <div className="cw-card">
                <h3>AI diagnosis</h3>
                <div className="cw-dx">{item.primary_diagnosis || 'No readable diagnosis'}</div>
                {item.differentials.length > 0 && <ul className="cw-list">{item.differentials.map((d) => <li key={d.condition}>{d.condition}</li>)}</ul>}
                {item.next_steps.length > 0 && <p className="cw-muted" style={{ marginTop: 8 }}>Next steps: {item.next_steps.join('; ')}</p>}
                <label className="cw-label" style={{ marginTop: 12 }}>Is the leading diagnosis right?</label>
                <RateButtons options={VERDICTS} value={form.verdict} onChange={(v) => setForm((f) => ({ ...f, verdict: v }))} />
                <label className="cw-label" style={{ marginTop: 12 }}>Overall clinical quality (1 = unsafe, 5 = would sign off)</label>
                <RateButtons options={[1, 2, 3, 4, 5].map((n) => [n, String(n)])} value={form.quality} onChange={(v) => setForm((f) => ({ ...f, quality: v }))} />
              </div>
              <div className="cw-card">
                <h3>AI alerts ({item.alerts.length})</h3>
                {item.alerts.length === 0 && <p className="cw-muted">This output raised no alerts.</p>}
                {item.alerts.map((a) => (
                  <div key={a.index} className={`cw-alert sev-${a.severity}`}>
                    <div className="top"><span className={`cw-pill pill-${a.severity}`}>{a.severity}</span><strong>{a.category}</strong><span className="cw-muted">· {a.source}</span></div>
                    <div>{a.description}</div>
                    <RateButtons options={[['valid', 'Real concern'], ['invalid', 'Not a real concern'], ['unsure', 'Unsure']]}
                      value={form.alerts[a.index]} onChange={(v) => setForm((f) => ({ ...f, alerts: { ...f.alerts, [a.index]: v } }))} />
                  </div>
                ))}
              </div>
              <div className="cw-card">
                <div className="cw-field"><label className="cw-label" htmlFor="rv-missed">Hazards the AI missed</label><textarea id="rv-missed" className="cw-textarea" maxLength={2000} value={form.missed} onChange={(e) => setForm((f) => ({ ...f, missed: e.target.value }))} /></div>
                <div className="cw-field"><label className="cw-label" htmlFor="rv-comments">Comments</label><textarea id="rv-comments" className="cw-textarea" maxLength={2000} value={form.comments} onChange={(e) => setForm((f) => ({ ...f, comments: e.target.value }))} /></div>
                <button className="cw-btn full" disabled={!complete || busy} onClick={submit}>Save and next</button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
