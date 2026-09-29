import React from 'react';
import { CheckCircle2, Circle, Hourglass, Loader2 } from 'lucide-react';

export default function AgentProgress({ job }) {
  if (!job) return null;
  const byName = Object.fromEntries(job.steps.map((s) => [s.agent, s]));
  const extra = job.steps.filter((s) => !job.planned.includes(s.agent)).map((s) => s.agent);
  const names = [...job.planned, ...extra];
  const waits = (job.events || []).filter((e) => e.type === 'rate_limit');
  const rl = job.rate_limit; // set by the server only while a wait is in progress
  const remaining = rl ? Math.ceil(rl.remaining_s) : 0;
  return (
    <div className="cw-card" aria-live="polite">
      <h3>Running · {job.elapsed_s}s</h3>
      {rl && remaining > 0 && (
        <div className="cw-banner info cw-ratelimit" role="status">
          <Hourglass size={16} />
          <div>
            <strong>Waiting for provider rate limit ({remaining}s)…</strong>
            {rl.provider} asked us to slow down; retry {rl.attempt}{rl.max_attempts ? ` of ${rl.max_attempts}` : ''} starts automatically.
          </div>
        </div>
      )}
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
      <p className="cw-muted" style={{ marginTop: 8, marginBottom: 0 }}>
        Checks run in parallel. If a check raises a serious concern, a revision step runs and the verifier/safety checks
        re-check the revised diagnosis. Rule-based contraindication checks run on every level.
        {waits.length > 0 && ` Rate-limit waits so far: ${waits.length} (${waits.reduce((t, e) => t + e.wait_s, 0)}s).`}
      </p>
    </div>
  );
}
