import React from 'react';
import { CheckCircle2, Circle, Loader2 } from 'lucide-react';

export default function AgentProgress({ job }) {
  if (!job) return null;
  const byName = Object.fromEntries(job.steps.map((s) => [s.agent, s]));
  const extra = job.steps.filter((s) => !job.planned.includes(s.agent)).map((s) => s.agent);
  const names = [...job.planned, ...extra];
  return (
    <div className="cw-card" aria-live="polite">
      <h3>Running · {job.elapsed_s}s</h3>
      <div className="cw-checks">
        {names.map((name) => {
          const s = byName[name];
          return (
            <div key={name}>
              <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                {s?.status === 'done' ? <CheckCircle2 size={14} color="var(--accent-green)" /> : s ? <Loader2 size={14} className="spin" /> : <Circle size={14} color="var(--text-muted)" />}
                {name}
              </span>
              <span className="cw-muted cw-num">{s?.status === 'done' ? `${s.latency_s}s` : s ? 'running' : 'waiting'}</span>
            </div>
          );
        })}
      </div>
      <p className="cw-muted" style={{ marginTop: 8, marginBottom: 0 }}>Checks run in parallel. A revision step is added if a check raises a serious concern.</p>
    </div>
  );
}
