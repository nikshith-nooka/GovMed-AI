import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ClipboardCopy, Info, Loader2, ShieldAlert, Stethoscope, Users } from 'lucide-react';
import './clinical.css';
import { EXAMPLE_CASES, runCaseWithProgress } from '../lib/api';
import AgentProgress from '../components/AgentProgress';

const LEVELS = [
  { code: 'G0', variant: 'V1', name: 'Fast, no checks', desc: 'Diagnosis only. Nothing is verified.' },
  { code: 'G1', variant: 'V2', name: 'Grounding check', desc: 'Flags claims not supported by the case text. Does not verify the diagnosis itself.' },
  { code: 'G3', variant: 'V4', name: 'Safety check', desc: 'Looks for contraindications and missed red flags. Alerts often; review each one.' },
  { code: 'G4', variant: 'V5', name: 'All checks', desc: 'Grounding, safety, consistency and a simulated attending review. Slowest.' },
];

const ENGINES = [
  { id: 'groq', label: 'Groq · GPT-OSS-120B (live)', live: true },
  { id: 'nvidia', label: 'NVIDIA NIM · Llama-3.2-11B (live)', live: true },
  { id: 'gemini', label: 'Google Gemini Flash (live)', live: true },
  { id: 'simulation', label: 'Demo generator (no API, not a real analysis)', live: false },
];

const EMPTY_FORM = { age: '', sex: '', chief_complaint: '', hpi: '', pmh: '', medications: '', allergies: '', vitals: '', labs: '' };

function pct(value) {
  return value == null ? '—' : `${Math.round(value * 100)}%`;
}

function Alerts({ alerts }) {
  if (!alerts.length) return <p className="cw-muted">No alerts were raised by the checks that ran.</p>;
  return alerts.map((a, i) => (
    <div key={i} className={`cw-alert sev-${a.severity}`}>
      <div className="top">
        <span className={`cw-pill pill-${a.severity}`}>{a.severity}</span>
        <strong>{a.category}</strong>
        <span className="cw-muted">· {a.source}</span>
      </div>
      <div>{a.description}</div>
      {a.action && <div className="act">Suggested action: {a.action}</div>}
    </div>
  ));
}

function Checks({ checks, notChecked }) {
  return (
    <>
      <div className="cw-checks">
        {checks.map((c) => (
          <div key={c.name}>
            <span>{c.name}</span>
            <span className={`cw-pill ${c.ran ? 'pill-ran' : 'pill-off'}`}>{c.ran ? c.outcome || 'RAN' : 'NOT RUN'}</span>
          </div>
        ))}
      </div>
      {notChecked.length > 0 && (
        <ul className="cw-list" style={{ marginTop: 10 }}>
          {notChecked.map((n) => <li key={n} className="cw-muted">{n}</li>)}
        </ul>
      )}
    </>
  );
}

function PhysicianView({ support }) {
  const { diagnosis, revision } = support;
  return (
    <>
      <div className="cw-card">
        <h3>Leading consideration</h3>
        <div className="cw-dx">{diagnosis.primary || 'No readable diagnosis returned'}</div>
        {diagnosis.justification && <p style={{ fontSize: '0.86rem', margin: '0 0 10px' }}>{diagnosis.justification}</p>}
        {diagnosis.differentials.map((d) => (
          <div key={d.condition} className="cw-diff">
            <div>
              <strong>{d.condition}</strong>
              {d.justification && <div className="cw-muted">{d.justification}</div>}
            </div>
            <div className="cw-bar" aria-hidden="true"><span style={{ width: `${Math.round((d.model_likelihood || 0) * 100)}%` }} /></div>
            <div className="cw-num cw-muted">{pct(d.model_likelihood)}</div>
          </div>
        ))}
        <p className="cw-muted" style={{ marginTop: 8 }}><Info size={12} /> {support.calibration_note}</p>
      </div>

      {revision.closed_loop && (
        <div className="cw-card">
          <h3>What the checks changed</h3>
          {revision.applied ? (
            <p style={{ fontSize: '0.86rem', margin: 0 }}>
              Reconsidered <strong>{revision.initial_diagnosis}</strong>; result: <strong>{revision.final_diagnosis}</strong>
              {revision.initial_diagnosis === revision.final_diagnosis && ' (kept after review)'}.
              {revision.rationale && <><br /><span className="cw-muted">{revision.rationale}</span></>}
            </p>
          ) : (
            <p className="cw-muted" style={{ margin: 0 }}>No serious concern was raised, so the diagnosis was not sent back for revision.</p>
          )}
          {revision.triggers.length > 0 && (
            <ul className="cw-list" style={{ marginTop: 8 }}>{revision.triggers.map((t) => <li key={t}>{t}</li>)}</ul>
          )}
        </div>
      )}

      <div className="cw-card">
        <h3>Alerts ({support.alerts.length})</h3>
        <Alerts alerts={support.alerts} />
      </div>

      <div className="cw-two">
        <div className="cw-card">
          <h3>Suggested next steps</h3>
          {support.next_steps.length ? <ul className="cw-list">{support.next_steps.map((s) => <li key={s}>{s}</li>)}</ul>
            : <p className="cw-muted">None returned.</p>}
        </div>
        <div className="cw-card" style={{ marginTop: 0 }}>
          <h3>What was checked</h3>
          <Checks checks={support.checks} notChecked={support.not_checked} />
        </div>
      </div>

      {(diagnosis.pertinent_positives.length > 0 || diagnosis.pertinent_negatives.length > 0) && (
        <div className="cw-card">
          <h3>Findings the AI extracted (verify against the chart)</h3>
          <div className="cw-row">
            <div><strong style={{ fontSize: '0.8rem' }}>Positives</strong><ul className="cw-list">{diagnosis.pertinent_positives.map((p) => <li key={p}>{p}</li>)}</ul></div>
            <div><strong style={{ fontSize: '0.8rem' }}>Negatives</strong><ul className="cw-list">{diagnosis.pertinent_negatives.map((p) => <li key={p}>{p}</li>)}</ul></div>
          </div>
        </div>
      )}
    </>
  );
}

function AssistantView({ support }) {
  const [done, setDone] = useState({});
  const [copied, setCopied] = useState(false);
  const h = support.handoff;
  const sbarText = [
    `S: ${h.situation || '—'}`,
    `B: ${h.background || '—'}`,
    `A: ${h.assessment}`,
    `R: ${h.recommendation}`,
    h.escalate.length ? `ESCALATE: ${h.escalate.join(' | ')}` : '',
    'Note: AI-generated, not clinician-reviewed.',
  ].filter(Boolean).join('\n');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sbarText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <>
      {support.escalate_now.length > 0 && (
        <div className="cw-banner high">
          <ShieldAlert size={18} />
          <div>
            <strong>Tell the responsible physician now</strong>
            <ul>{support.escalate_now.map((e) => <li key={e}>{e}</li>)}</ul>
          </div>
        </div>
      )}
      <div className="cw-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <h3 style={{ margin: 0 }}>SBAR handoff draft</h3>
          <button className="cw-btn ghost small" onClick={copy}><ClipboardCopy size={14} />{copied ? 'Copied' : 'Copy'}</button>
        </div>
        <dl className="cw-sbar">
          <dt>Situation</dt><dd>{h.situation || '—'}</dd>
          <dt>Background</dt><dd>{h.background || '—'}</dd>
          <dt>Assessment</dt><dd>{h.assessment}</dd>
          <dt>Recommendation</dt><dd>{h.recommendation}</dd>
        </dl>
      </div>
      <div className="cw-card">
        <h3>Task checklist</h3>
        {support.next_steps.length ? support.next_steps.map((s) => (
          <label key={s} className="cw-check">
            <input type="checkbox" checked={!!done[s]} onChange={() => setDone((d) => ({ ...d, [s]: !d[s] }))} />
            <span style={{ textDecoration: done[s] ? 'line-through' : 'none' }}>{s}</span>
          </label>
        )) : <p className="cw-muted">No tasks returned.</p>}
        <p className="cw-muted" style={{ marginTop: 10 }}>Orders and medications still need a clinician's sign-off.</p>
      </div>
      <div className="cw-card">
        <h3>Not checked by the AI</h3>
        {support.not_checked.length ? <ul className="cw-list">{support.not_checked.map((n) => <li key={n}>{n}</li>)}</ul>
          : <p className="cw-muted">All checks ran at this level.</p>}
      </div>
    </>
  );
}

export default function ClinicianWorkspace({ cases = [], prefill = null }) {
  const [role, setRole] = useState('physician');
  const [form, setForm] = useState(EMPTY_FORM);
  const [level, setLevel] = useState('G1');
  const [closedLoop, setClosedLoop] = useState(true);
  const [engine, setEngine] = useState('simulation');
  const [providers, setProviders] = useState({});
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [latency, setLatency] = useState({});
  const timer = useRef(null);

  useEffect(() => {
    fetch('/api/providers')
      .then((r) => (r.ok ? r.json() : {}))
      .then((p) => {
        setProviders(p);
        const firstLive = ENGINES.find((e) => e.live && p[e.id]?.available);
        if (firstLive) setEngine(firstLive.id);
      })
      .catch(() => {});
    fetch('/api/research/findings')
      .then((r) => (r.ok ? r.json() : null))
      .then((rep) => {
        if (!rep) return;
        const map = {};
        rep.variants.forEach((v) => { map[v.variant_id] = v.e2e_latency_p50_s; });
        setLatency(map);
      })
      .catch(() => {});
    return () => clearInterval(timer.current);
  }, []);

  useEffect(() => {
    if (!prefill) return;
    setForm({ ...EMPTY_FORM, ...Object.fromEntries(Object.keys(EMPTY_FORM).map((k) => [k, prefill[k] || ''])) });
    setResult(null);
    setError(null);
  }, [prefill]);

  const examples = useMemo(() => cases.filter((c) => c.question), [cases]);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const canRun = form.chief_complaint.trim().length >= 2 && form.hpi.trim().length >= 5 && !loading;

  const loadExample = (id) => {
    const c = examples.find((x) => x.id === id);
    if (!c) return;
    const firstSentence = c.question.split(/(?<=[.?!])\s/)[0].slice(0, 160);
    setForm({ ...EMPTY_FORM, chief_complaint: firstSentence, hpi: c.question.slice(0, 8000) });
    setResult(null);
  };

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setJob(null);
    setElapsed(0);
    const started = Date.now();
    timer.current = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    try {
      const body = await runCaseWithProgress({
        ...form,
        governance_level: level,
        closed_loop: closedLoop,
        provider: engine,
        use_live_llm: engine !== 'simulation',
      }, setJob);
      setResult(body);
    } catch (e) {
      setError(e.message);
    } finally {
      clearInterval(timer.current);
      setLoading(false);
    }
  };

  const support = result?.decision_support;
  const expected = latency[LEVELS.find((l) => l.code === level)?.variant];

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Clinician Workspace</h2>
          <p className="cw-sub">AI decision support for physicians and clinical assistants. It shows what was checked, what was not, and what needs a human decision. It does not replace clinical judgment.</p>
        </div>
        <div className="cw-seg" role="group" aria-label="View for">
          <button aria-pressed={role === 'physician'} onClick={() => setRole('physician')}><Stethoscope size={13} /> Physician</button>
          <button aria-pressed={role === 'assistant'} onClick={() => setRole('assistant')}><Users size={13} /> Clinical assistant</button>
        </div>
      </div>

      <div className="cw-grid">
        <div>
          <div className="cw-card">
            <h3>Patient</h3>
            <div className="cw-rate" style={{ marginTop: 0, marginBottom: 10 }} aria-label="Example patients">
              {EXAMPLE_CASES.map((ex) => (
                <button key={ex.id} type="button" onClick={() => { setForm({ ...EMPTY_FORM, ...Object.fromEntries(Object.keys(EMPTY_FORM).map((k) => [k, ex[k] || ''])) }); setResult(null); setError(null); }}>
                  {ex.label}
                </button>
              ))}
              <button type="button" onClick={() => { setForm(EMPTY_FORM); setResult(null); setError(null); }}>Clear</button>
            </div>
            {examples.length > 0 && (
              <div className="cw-field">
                <label className="cw-label" htmlFor="cw-example">Load a benchmark case</label>
                <select id="cw-example" className="cw-select" defaultValue="" onChange={(e) => loadExample(e.target.value)}>
                  <option value="" disabled>Choose an example…</option>
                  {examples.map((c) => <option key={c.id} value={c.id}>{c.id} · {c.specialty}</option>)}
                </select>
              </div>
            )}
            <div className="cw-row" style={{ marginTop: 10 }}>
              <div><label className="cw-label" htmlFor="cw-age">Age</label><input id="cw-age" className="cw-input" value={form.age} onChange={set('age')} maxLength={20} /></div>
              <div><label className="cw-label" htmlFor="cw-sex">Sex</label><input id="cw-sex" className="cw-input" value={form.sex} onChange={set('sex')} maxLength={20} /></div>
            </div>
            <div className="cw-field"><label className="cw-label" htmlFor="cw-cc">Chief complaint <span className="req">*</span></label><input id="cw-cc" className="cw-input" value={form.chief_complaint} onChange={set('chief_complaint')} maxLength={500} /></div>
            <div className="cw-field"><label className="cw-label" htmlFor="cw-hpi">History of present illness <span className="req">*</span></label><textarea id="cw-hpi" className="cw-textarea" style={{ minHeight: 110 }} value={form.hpi} onChange={set('hpi')} maxLength={8000} /></div>
            <div className="cw-field"><label className="cw-label" htmlFor="cw-pmh">Past medical history</label><textarea id="cw-pmh" className="cw-textarea" value={form.pmh} onChange={set('pmh')} maxLength={4000} /></div>
            <div className="cw-row" style={{ marginTop: 10 }}>
              <div><label className="cw-label" htmlFor="cw-meds">Medications</label><textarea id="cw-meds" className="cw-textarea" value={form.medications} onChange={set('medications')} maxLength={4000} /></div>
              <div><label className="cw-label" htmlFor="cw-allergies">Allergies</label><textarea id="cw-allergies" className="cw-textarea" value={form.allergies} onChange={set('allergies')} maxLength={1000} /></div>
            </div>
            <div className="cw-row" style={{ marginTop: 10 }}>
              <div><label className="cw-label" htmlFor="cw-vitals">Vitals</label><textarea id="cw-vitals" className="cw-textarea" value={form.vitals} onChange={set('vitals')} maxLength={1000} /></div>
              <div><label className="cw-label" htmlFor="cw-labs">Labs / findings</label><textarea id="cw-labs" className="cw-textarea" value={form.labs} onChange={set('labs')} maxLength={4000} /></div>
            </div>
          </div>

          <div className="cw-card">
            <h3>How much checking</h3>
            <div className="cw-level" role="radiogroup" aria-label="Check level">
              {LEVELS.map((l) => (
                <label key={l.code} className={level === l.code ? 'on' : ''}>
                  <input type="radio" name="level" checked={level === l.code} onChange={() => setLevel(l.code)} />
                  <span><strong>{l.name}</strong><br /><span className="meta">{l.desc}{latency[l.variant] ? ` · ~${Math.round(latency[l.variant])}s on the benchmark model (NVIDIA 11B); Groq is usually faster` : ''}</span></span>
                </label>
              ))}
            </div>
            <label className="cw-check">
              <input type="checkbox" checked={closedLoop && level !== 'G0'} disabled={level === 'G0'} onChange={(e) => setClosedLoop(e.target.checked)} />
              <span>Send the diagnosis back for revision when a check raises a serious concern</span>
            </label>
            <div className="cw-field" style={{ marginTop: 12 }}>
              <label className="cw-label" htmlFor="cw-engine">Engine</label>
              <select id="cw-engine" className="cw-select" value={engine} onChange={(e) => setEngine(e.target.value)}>
                {ENGINES.map((e) => {
                  const unavailable = e.live && !providers[e.id]?.available;
                  return <option key={e.id} value={e.id} disabled={unavailable}>{e.label}{unavailable ? ' — no API key' : ''}</option>;
                })}
              </select>
            </div>
            <button className="cw-btn full" disabled={!canRun} onClick={run}>
              {loading ? <><Loader2 size={16} className="spin" /> Running… {elapsed}s</> : 'Analyze case'}
            </button>
            {loading && engine !== 'simulation' && (
              <p className="cw-muted" style={{ marginTop: 8 }}>Live runs call several agents in sequence{expected && engine === 'nvidia' ? `; this level typically takes about ${Math.round(expected)}s` : ''}.</p>
            )}
          </div>
        </div>

        <div className="cw-stack" aria-live="polite">
          {error && <div className="cw-banner error"><AlertTriangle size={18} /><div><strong>No result</strong>{error}</div></div>}
          {loading && <AgentProgress job={job} />}
          {!result && !error && !loading && (
            <div className="cw-card cw-empty">Enter a chief complaint and history, choose how much checking you want, then analyze.</div>
          )}
          {result?.notice && <div className="cw-banner demo"><Info size={18} /><div><strong>Demo output</strong>{result.notice}</div></div>}
          {support && (
            <div className={`cw-banner ${support.attention === 'HIGH' ? 'high' : 'standard'}`}>
              {support.attention === 'HIGH' ? <ShieldAlert size={18} /> : <Info size={18} />}
              <div>
                <strong>{support.attention === 'HIGH' ? 'Needs careful review' : 'Standard review'}</strong>
                <ul>{support.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
            </div>
          )}
          {support && (role === 'physician' ? <PhysicianView support={support} /> : <AssistantView support={support} />)}
          {support && (
            <div className="cw-card">
              <div className="cw-telemetry">
                <span>{result.model_used}</span>
                <span>{result.governance_label}</span>
                <span>{result.telemetry.latency_seconds}s</span>
                <span>{result.telemetry.tokens_used?.toLocaleString()} tokens</span>
                <span>${result.telemetry.cost_usd?.toFixed(5)}</span>
              </div>
              <p className="cw-muted" style={{ marginTop: 8, marginBottom: 0 }}>{support.disclaimer}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
