import React, { useState } from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';
import { fmt, useApi } from '../lib/api';
import './clinical.css';

const AGENTS = {
  'Research Agent': { does: 'Extracts chief complaint, history, vitals, labs, pertinent positives and negatives from the case text.', output: 'Structured findings (JSON)' },
  'Diagnosis Agent': { does: 'Ranks a differential diagnosis with a stated likelihood for each item, and suggests next steps.', output: 'Primary diagnosis, differential, next steps' },
  'Consistency Checker': { does: 'Checks that the diagnosis fits the extracted findings and flags contradictions.', output: 'Consistency status and inconsistencies' },
  'Verifier Agent': { does: 'Compares each claim against the original case text and flags anything not supported by it.', output: 'Hallucination flag and flagged claims' },
  'Safety Validator': { does: 'Looks for contraindications, missed red flags and unsafe delays in the proposed plan.', output: 'Safety flags with severity and mitigation' },
  'HITL Simulator': { does: 'An LLM imitating an attending physician who approves, requests revision or rejects. Not a human.', output: 'Decision, critique, required amendments' },
  'Report Agent': { does: 'Writes a SOAP-style note that includes the governance findings.', output: 'Clinical note' },
};

const LEVELS = [
  { code: 'G0', variant: 'V1', name: 'No checks', layers: ['Research Agent', 'Diagnosis Agent', 'Report Agent'] },
  { code: 'G1', variant: 'V2', name: 'Grounding verifier', layers: ['Research Agent', 'Diagnosis Agent', 'Verifier Agent', 'Report Agent'] },
  { code: 'G2', variant: 'V3', name: 'Simulated attending review', layers: ['Research Agent', 'Diagnosis Agent', 'HITL Simulator', 'Report Agent'] },
  { code: 'G3', variant: 'V4', name: 'Safety validator', layers: ['Research Agent', 'Diagnosis Agent', 'Safety Validator', 'Report Agent'] },
  { code: 'G4', variant: 'V5', name: 'All checks', layers: ['Research Agent', 'Diagnosis Agent', 'Consistency Checker', 'Verifier Agent', 'Safety Validator', 'HITL Simulator', 'Report Agent'] },
];

export default function AgentPipeline() {
  const [levelCode, setLevelCode] = useState('G4');
  const [agent, setAgent] = useState('Diagnosis Agent');
  const { data: report, loading } = useApi('/api/research/findings');
  const level = LEVELS.find((l) => l.code === levelCode);
  const variant = report?.variants.find((v) => v.variant_id === level.variant);
  const agentStats = Object.fromEntries((report?.latency_by_agent || []).map((a) => [a.agent, a]));
  const selectedStats = agentStats[agent];

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <h2 className="cw-title">Agent Pipeline & Governance Levels</h2>
          <p className="cw-sub">Which agents run at each check level, in order, with latency and tokens measured on the benchmark model. Research and Diagnosis always run; checks are added on top.</p>
        </div>
      </div>

      <div className="cw-tabs cw-seg" role="tablist" style={{ display: 'inline-flex' }}>
        {LEVELS.map((l) => <button key={l.code} role="tab" aria-pressed={levelCode === l.code} onClick={() => setLevelCode(l.code)}>{l.code} · {l.name}</button>)}
      </div>

      <div className="cw-card">
        <h3>{level.code} pipeline ({level.variant} in the benchmark)</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
          {level.layers.map((name, i) => (
            <React.Fragment key={name}>
              <button className="cw-card cw-tile" style={{ marginTop: 0, padding: '10px 12px', borderColor: agent === name ? 'var(--accent-green)' : undefined }} onClick={() => setAgent(name)}>
                <strong style={{ fontSize: '0.84rem' }}>{name}</strong>
                <div className="cw-muted">{agentStats[name] ? `${fmt(agentStats[name].mean_s, 1)} s mean` : ''}</div>
              </button>
              {i < level.layers.length - 1 && <ArrowRight size={16} className="cw-muted" />}
            </React.Fragment>
          ))}
        </div>
        <p className="cw-muted" style={{ marginTop: 10 }}>
          With closed loop on, a serious concern from any check sends the diagnosis back to the Diagnosis Agent for one revision before the report is written.
        </p>
      </div>

      <div className="cw-cols-32" style={{ marginTop: 14 }}>
        <div className="cw-card">
          <h3>{agent}</h3>
          <p style={{ fontSize: '0.86rem', marginTop: 0 }}>{AGENTS[agent]?.does}</p>
          <p className="cw-muted">Output: {AGENTS[agent]?.output}</p>
          {loading ? <Loader2 className="spin" /> : selectedStats ? (
            <div className="cw-checks" style={{ marginTop: 10 }}>
              <div><span>Calls in benchmark</span><strong className="cw-num">{selectedStats.calls}</strong></div>
              <div><span>Mean / p95 / max latency</span><strong className="cw-num">{fmt(selectedStats.mean_s, 1)} / {fmt(selectedStats.p95_s, 1)} / {fmt(selectedStats.max_s, 1)} s</strong></div>
              <div><span>Mean tokens per call</span><strong className="cw-num">{fmt(selectedStats.mean_tokens, 0)}</strong></div>
              <div><span>Share of a run's time</span><strong className="cw-num">{Math.round((selectedStats.mean_share_of_run || 0) * 100)}%</strong></div>
            </div>
          ) : <p className="cw-muted">Not measured in the stored benchmark.</p>}
        </div>
        <div className="cw-card">
          <h3>{level.code} measured outcome</h3>
          {variant ? (
            <div className="cw-checks">
              <div><span>Accuracy (scorable cases)</span><strong className="cw-num">{fmt(variant.accuracy_valid_gold)}</strong></div>
              <div><span>Diagnosis changed vs. no checks</span><strong className="cw-num">{fmt(variant.diagnosis_changed_vs_v1_pct, 1)}%</strong></div>
              <div><span>Median / p95 latency</span><strong className="cw-num">{fmt(variant.e2e_latency_p50_s, 0)} / {fmt(variant.e2e_latency_p95_s, 0)} s</strong></div>
              <div><span>Tokens per case</span><strong className="cw-num">{fmt(variant.tokens_mean, 0)}</strong></div>
              <div><span>Cost per case</span><strong className="cw-num">${fmt(variant.cost_mean_usd, 5)}</strong></div>
              <div><span>Safety alerts / hallucination flags</span><strong className="cw-num">{variant.safety_alerts_total} / {variant.hallucination_flags_total}</strong></div>
            </div>
          ) : <p className="cw-muted">{loading ? 'Loading…' : 'Run the analysis to see measured outcomes.'}</p>}
          <p className="cw-muted" style={{ marginTop: 10 }}>These runs were open loop: checks annotated the output but never changed the diagnosis.</p>
        </div>
      </div>
    </div>
  );
}
