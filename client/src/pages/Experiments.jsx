import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, Download, Loader2, Play, Square } from 'lucide-react';
import { fmt, useApi } from '../lib/api';
import './clinical.css';

const LEVELS = [['G0', 'No checks'], ['G1', 'Grounding verifier'], ['G2', 'Simulated attending'], ['G3', 'Safety validator'], ['G4', 'All checks']];
const ENGINES = [['groq', 'Groq · GPT-OSS-120B'], ['nvidia', 'NVIDIA · Llama-3.2-11B'], ['gemini', 'Gemini Flash'], ['simulation', 'Demo generator (no API)']];
const PAGE = 25;

function toCsv(rows) {
  const cols = ['case_id', 'dataset', 'governance', 'model', 'gold_diagnosis', 'gold_valid', 'primary_diagnosis', 'accuracy',
    'alerts', 'high_alerts', 'hallucination_flagged', 'revision_applied', 'initial_diagnosis', 'latency_s', 'tokens', 'cost_usd'];
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  return [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n');
}

function summarize(rows) {
  const by = {};
  rows.forEach((r) => {
    const s = (by[r.governance] ||= { governance: r.governance, n: 0, scored: 0, acc: 0, latency: 0, cost: 0, alerts: 0, revised: 0 });
    s.n += 1; s.latency += r.latency_s; s.cost += r.cost_usd; s.alerts += r.alerts; s.revised += r.revision_applied ? 1 : 0;
    if (r.accuracy != null) { s.scored += 1; s.acc += r.accuracy; }
  });
  return Object.values(by).map((s) => ({ ...s, acc: s.scored ? s.acc / s.scored : null, latency: s.latency / s.n }));
}

export default function Experiments({ cases = [] }) {
  const providers = useApi('/api/providers');
  const [dataset, setDataset] = useState('all');
  const [scorableOnly, setScorableOnly] = useState(true);
  const [count, setCount] = useState(5);
  const [levels, setLevels] = useState(['G0', 'G4']);
  const [engine, setEngine] = useState('simulation');
  const [closedLoop, setClosedLoop] = useState(true);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [results, setResults] = useState([]);
  const [runError, setRunError] = useState(null);
  const stopRef = useRef(false);

  useEffect(() => {
    const p = providers.data;
    if (!p) return;
    const live = ENGINES.find(([id]) => id !== 'simulation' && p[id]?.available);
    if (live) setEngine(live[0]);
  }, [providers.data]);

  const pool = useMemo(() => cases.filter((c) => (dataset === 'all' || c.id.startsWith(dataset))
    && (!scorableOnly || !(c.gold_diagnosis || '').toLowerCase().startsWith('clinical diagnostic note'))), [cases, dataset, scorableOnly]);
  const selected = pool.slice(0, Math.max(1, Math.min(count, pool.length)));
  const totalRuns = selected.length * levels.length;
  const live = engine !== 'simulation';

  const toggleLevel = (code) => setLevels((ls) => (ls.includes(code) ? ls.filter((l) => l !== code) : [...ls, code]));

  const run = async () => {
    stopRef.current = false;
    setRunning(true);
    setRunError(null);
    setResults([]);
    setProgress({ done: 0, total: totalRuns });
    let done = 0;
    for (const c of selected) {
      for (const level of levels) {
        if (stopRef.current) break;
        try {
          const res = await fetch('/api/experiments/run-case', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ case_id: c.id, governance_level: level, provider: engine, closed_loop: closedLoop }),
          });
          const body = await res.json();
          if (!res.ok) throw new Error(body.detail || `Failed (${res.status})`);
          setResults((rs) => [...rs, body]);
        } catch (e) {
          setRunError(`${c.id} ${level}: ${e.message}`);
          stopRef.current = true;
        }
        done += 1;
        setProgress({ done, total: totalRuns });
      }
      if (stopRef.current) break;
    }
    setRunning(false);
  };

  const download = () => {
    const blob = new Blob([toCsv(results)], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `govbench_experiment_${new Date().toISOString().slice(0, 19)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const [variant, setVariant] = useState('All');
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const stored = useApi(`/api/runs?limit=${PAGE}&offset=${offset}${variant !== 'All' ? `&variant=${variant}` : ''}`);
  const history = useApi(`/api/experiments/runs?limit=50&refresh=${running ? 0 : results.length}`);
  const storedRows = (stored.data?.runs || []).filter((r) => !search || r.case_id.includes(search) || (r.primary_diagnosis || '').toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Experiments</h2>
          <p className="cw-sub">Run benchmark cases through the real pipeline at chosen check levels, scored against their gold labels. Results are saved to results/ui_experiments.db, separate from the main benchmark.</p>
        </div>
      </div>

      <div className="cw-grid">
        <div className="cw-card">
          <h3>Set up a run</h3>
          <div className="cw-field">
            <label className="cw-label" htmlFor="ex-ds">Dataset</label>
            <select id="ex-ds" className="cw-select" value={dataset} onChange={(e) => setDataset(e.target.value)}>
              <option value="all">All datasets</option><option value="medqa">MedQA</option><option value="pubmedqa">PubMedQA</option><option value="meddialog">MedDialog</option>
            </select>
          </div>
          <label className="cw-check"><input type="checkbox" checked={scorableOnly} onChange={(e) => setScorableOnly(e.target.checked)} /><span>Only cases with a real diagnosis label (scorable)</span></label>
          <div className="cw-field" style={{ marginTop: 10 }}>
            <label className="cw-label" htmlFor="ex-n">Number of cases ({pool.length} available)</label>
            <input id="ex-n" className="cw-input" type="number" min={1} max={Math.min(50, pool.length || 1)} value={count} onChange={(e) => setCount(Number(e.target.value) || 1)} />
          </div>
          <label className="cw-label" style={{ marginTop: 10 }}>Check levels</label>
          {LEVELS.map(([code, name]) => (
            <label key={code} className="cw-check" style={{ marginTop: 4 }}>
              <input type="checkbox" checked={levels.includes(code)} onChange={() => toggleLevel(code)} /><span>{code} · {name}</span>
            </label>
          ))}
          <label className="cw-check"><input type="checkbox" checked={closedLoop} onChange={(e) => setClosedLoop(e.target.checked)} /><span>Closed loop (revise the diagnosis on serious concerns)</span></label>
          <div className="cw-field" style={{ marginTop: 10 }}>
            <label className="cw-label" htmlFor="ex-engine">Engine</label>
            <select id="ex-engine" className="cw-select" value={engine} onChange={(e) => setEngine(e.target.value)}>
              {ENGINES.map(([id, label]) => {
                const off = id !== 'simulation' && !providers.data?.[id]?.available;
                return <option key={id} value={id} disabled={off}>{label}{off ? ' — no API key' : ''}</option>;
              })}
            </select>
          </div>
          <p className="cw-muted" style={{ marginTop: 8 }}>
            {totalRuns} pipeline run(s){live ? `, each 4-8 live model calls. Uses your ${engine} API credits.` : '. Demo output is not a real analysis.'}
          </p>
          {running ? (
            <button className="cw-btn full ghost" onClick={() => { stopRef.current = true; }}><Square size={14} /> Stop after current case</button>
          ) : (
            <button className="cw-btn full" disabled={!levels.length || !selected.length} onClick={run}><Play size={14} /> Run {totalRuns} case run(s)</button>
          )}
        </div>

        <div className="cw-stack">
          {runError && <div className="cw-banner error"><AlertTriangle size={18} /><div><strong>Run stopped</strong>{runError}</div></div>}
          {(running || results.length > 0) && (
            <div className="cw-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                <h3 style={{ margin: 0 }}>{running ? <><Loader2 size={12} className="spin" /> Running</> : 'Finished'} · {progress.done}/{progress.total}</h3>
                <button className="cw-btn ghost small" disabled={!results.length} onClick={download}><Download size={14} /> CSV</button>
              </div>
              <div className="cw-progress" style={{ margin: '10px 0' }}><span style={{ width: `${progress.total ? (100 * progress.done) / progress.total : 0}%` }} /></div>
              <div className="cw-table-wrap">
                <table className="cw-table">
                  <thead><tr><th>Level</th><th>Runs</th><th>Accuracy (scored)</th><th>Mean latency (s)</th><th>Alerts</th><th>Revised</th><th>Cost (USD)</th></tr></thead>
                  <tbody>{summarize(results).map((s) => (
                    <tr key={s.governance}><td>{s.governance}</td><td className="cw-num">{s.n}</td><td className="cw-num">{fmt(s.acc)} ({s.scored})</td><td className="cw-num">{fmt(s.latency, 1)}</td><td className="cw-num">{s.alerts}</td><td className="cw-num">{s.revised}</td><td className="cw-num">{fmt(s.cost, 5)}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
          {results.length > 0 && (
            <div className="cw-card">
              <h3>Case results</h3>
              <div className="cw-table-wrap">
                <table className="cw-table">
                  <thead><tr><th>Case</th><th>Level</th><th>Gold</th><th>AI diagnosis</th><th>Accuracy</th><th>Alerts</th><th>Revised</th><th>s</th></tr></thead>
                  <tbody>{results.map((r) => (
                    <tr key={r.run_id}>
                      <td>{r.case_id}</td><td>{r.governance.split(' ')[0]}</td>
                      <td>{r.gold_valid ? r.gold_diagnosis : <span className="cw-muted">not scorable</span>}</td>
                      <td>{r.primary_diagnosis || <span className="cw-muted">unreadable</span>}{r.revision_applied && r.initial_diagnosis !== r.primary_diagnosis && <div className="cw-muted">was: {r.initial_diagnosis}</div>}</td>
                      <td className="cw-num">{fmt(r.accuracy, 2)}</td><td className="cw-num">{r.alerts} ({r.high_alerts} high)</td>
                      <td>{r.revision_applied ? 'yes' : 'no'}</td><td className="cw-num">{fmt(r.latency_s, 1)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
          {!running && !results.length && <div className="cw-card cw-empty">Choose cases and levels, then run. Results appear here as each case finishes.</div>}
        </div>
      </div>

      <div className="cw-card" style={{ marginTop: 14 }}>
        <h3>Your saved experiment runs ({history.data?.total ?? 0})</h3>
        {history.data?.runs?.length ? (
          <div className="cw-table-wrap">
            <table className="cw-table">
              <thead><tr><th>Case</th><th>Variant</th><th>Model</th><th>AI diagnosis</th><th>Accuracy</th><th>Safety alerts</th><th>Revised</th><th>When</th></tr></thead>
              <tbody>{history.data.runs.map((r) => (
                <tr key={r.id}><td>{r.case_id}</td><td>{r.variant_id}</td><td>{r.provider} / {r.model}</td><td>{r.primary_diagnosis}</td>
                  <td className="cw-num">{r.gold_label_valid ? fmt(r.diagnostic_accuracy_score, 2) : '—'}</td><td className="cw-num">{r.safety_violations_detected}</td>
                  <td>{r.revision_applied ? 'yes' : 'no'}</td><td className="cw-muted">{new Date(r.timestamp * 1000).toLocaleString()}</td></tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="cw-muted">None yet.</p>}
      </div>

      <div className="cw-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Stored benchmark runs ({stored.data?.total ?? '…'})</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="cw-input" style={{ width: 200 }} placeholder="Filter this page…" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Filter stored runs" />
            <select className="cw-select" style={{ width: 120 }} value={variant} onChange={(e) => { setVariant(e.target.value); setOffset(0); }} aria-label="Variant">
              {['All', 'V1', 'V2', 'V3', 'V4', 'V5'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </div>
        </div>
        {stored.error && <p className="cw-muted">{stored.error}</p>}
        <div className="cw-table-wrap" style={{ marginTop: 10 }}>
          <table className="cw-table">
            <thead><tr><th>Case</th><th>Dataset</th><th>Variant</th><th>AI diagnosis</th><th>Gold</th><th>Measured accuracy</th><th>Safety alerts</th><th>Hallucination flag</th><th>Tokens</th></tr></thead>
            <tbody>{storedRows.map((r) => (
              <tr key={r.id}>
                <td>{r.case_id}</td><td>{r.dataset}</td><td>{r.variant_id}</td><td>{r.primary_diagnosis || <span className="cw-muted">unreadable</span>}</td>
                <td>{r.gold_valid ? r.gold_diagnosis : <span className="cw-muted">not scorable</span>}</td>
                <td className="cw-num">{fmt(r.measured_accuracy, 2)}</td><td className="cw-num">{r.safety_alerts ?? '—'}</td>
                <td>{r.hallucination_flagged == null ? '—' : r.hallucination_flagged ? 'yes' : 'no'}</td><td className="cw-num">{r.total_tokens}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
          <button className="cw-btn ghost small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>Previous</button>
          <span className="cw-muted">{offset + 1}–{Math.min(offset + PAGE, stored.data?.total ?? 0)}</span>
          <button className="cw-btn ghost small" disabled={!stored.data || offset + PAGE >= stored.data.total} onClick={() => setOffset(offset + PAGE)}>Next</button>
        </div>
      </div>
    </div>
  );
}
