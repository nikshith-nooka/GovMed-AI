// Research charts drawn as SVG at the container's real width (so text stays legible on phones, unlike a scaled
// viewBox). Colours are CSS tokens (--chart-*), so light/dark/contrast modes follow the theme. Every mark is a
// focusable element with a tooltip; every chart has a text summary, and the pages keep a table of the same numbers.
import React, { useLayoutEffect, useRef, useState } from 'react';

function useWidth(fallback = 640) {
  const ref = useRef(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const update = () => setWidth(Math.max(260, Math.round(el.getBoundingClientRect().width) || fallback));
    update();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, width];
}

const scale = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);

/** "Nice" tick values covering [lo, hi]. */
function ticks(lo, hi, count = 5) {
  const span = hi - lo || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

const fmtTick = (v) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}k` : `${+v.toFixed(3)}`);

/** Card body shared by every chart: title, summary for assistive tech, unavailable state, tooltip layer. */
export function ChartFrame({ title, subtitle, summary, unavailable, legend, children, height }) {
  const [ref, width] = useWidth();
  const [tip, setTip] = useState(null);
  return (
    <figure className="cw-chart" style={{ margin: 0 }}>
      <div className="cw-chart-head">
        <figcaption>
          <h3 style={{ margin: 0 }}>{title}</h3>
          {subtitle && <div className="cw-muted" style={{ marginTop: 2 }}>{subtitle}</div>}
        </figcaption>
        {legend && !unavailable && <ul className="cw-legend" aria-label="Legend">{legend}</ul>}
      </div>
      <div ref={ref} className="cw-chart-plot" style={{ minHeight: unavailable ? 0 : height }}>
        {unavailable ? (
          <div className="cw-chart-empty" role="status">{unavailable}</div>
        ) : (
          <>
            <span className="visually-hidden">{summary}</span>
            {children({ width, showTip: setTip, hideTip: () => setTip(null) })}
            {tip && (
              <div className="cw-tooltip" role="tooltip" style={{ left: Math.min(tip.x, width - 180), top: tip.y }}>
                {tip.lines.map((l, i) => <div key={i} className={i === 0 ? 'cw-tooltip-title' : undefined}>{l}</div>)}
              </div>
            )}
          </>
        )}
      </div>
    </figure>
  );
}

export const LegendItem = ({ shape = 'circle', color, children }) => (
  <li><svg width="12" height="12" aria-hidden="true">{shape === 'square'
    ? <rect x="1" y="1" width="10" height="10" rx="2" fill={color} />
    : shape === 'line' ? <rect x="0" y="5" width="12" height="2" fill={color} />
      : <circle cx="6" cy="6" r="5" fill={color} />}</svg>{children}</li>
);

/** Interactive mark: hover and keyboard focus show the same tooltip. */
function Mark({ tip, showTip, hideTip, label, x, y, children }) {
  const show = () => showTip({ x: x + 12, y: Math.max(0, y - 10), lines: tip });
  return (
    <g tabIndex={0} role="img" aria-label={label} className="cw-mark"
      onMouseEnter={show} onMouseLeave={hideTip} onFocus={show} onBlur={hideTip}>{children}</g>
  );
}

const AxisX = ({ x, ticksV, y, top, fmt = fmtTick, label, width, left }) => (
  <g className="cw-axis" aria-hidden="true">
    {ticksV.map((t) => (
      <g key={t}>
        <line x1={x(t)} x2={x(t)} y1={top} y2={y} className="cw-grid" />
        <text x={x(t)} y={y + 16} textAnchor="middle">{fmt(t)}</text>
      </g>
    ))}
    {label && <text x={left + (width - left) / 2} y={y + 34} textAnchor="middle" className="cw-axis-title">{label}</text>}
  </g>
);

/**
 * Horizontal dot plot with 95% intervals, one row per configuration.
 * rows: [{ id, label, value, lo, hi, group: 'open' | 'closed' }]
 */
export function DotPlotCI({ rows, reference, xLabel, domain, fmt = (v) => v.toFixed(3), ...frame }) {
  const valid = rows.filter((r) => r.value != null);
  // A dot plot needs no zero baseline: fit the axis to the estimates and their intervals (steps of 0.05), so the
  // differences the reader must judge are not compressed into a sliver of a 0-1 scale.
  if (!domain && valid.length) {
    const lo = Math.min(...valid.map((r) => r.lo ?? r.value), reference ?? Infinity);
    const hi = Math.max(...valid.map((r) => r.hi ?? r.value), reference ?? -Infinity);
    domain = [Math.max(0, Math.floor((lo - 0.02) * 20) / 20), Math.min(1, Math.ceil((hi + 0.02) * 20) / 20)];
  }
  domain = domain || [0, 1];
  const rowH = 34;
  const height = valid.length * rowH + 52;
  return (
    <ChartFrame {...frame} height={height} unavailable={frame.unavailable || (!valid.length && 'No configuration has a measured value in this experiment.')}>
      {({ width, showTip, hideTip }) => {
        const narrow = width < 480;
        const left = narrow ? 92 : 190;
        const right = 16;
        const x = scale(domain[0], domain[1], left, width - right);
        const plotBottom = valid.length * rowH + 6;
        return (
          <svg width={width} height={height} className="cw-svg">
            <AxisX x={x} ticksV={ticks(domain[0], domain[1], narrow ? 4 : 6)} y={plotBottom} top={0} label={xLabel} width={width - right} left={left} />
            {reference != null && <line x1={x(reference)} x2={x(reference)} y1={0} y2={plotBottom} className="cw-ref-line" />}
            {valid.map((r, i) => {
              const cy = i * rowH + rowH / 2;
              const color = r.group === 'closed' ? 'var(--chart-primary)' : 'var(--chart-neutral)';
              const ci = r.lo != null && r.hi != null;
              return (
                <Mark key={r.id} showTip={showTip} hideTip={hideTip} x={x(r.value)} y={cy}
                  label={`${r.label}: ${fmt(r.value)}${ci ? `, 95% interval ${fmt(r.lo)} to ${fmt(r.hi)}` : ''}`}
                  tip={[r.label, `${fmt(r.value)}${ci ? `  (95% CI ${fmt(r.lo)}–${fmt(r.hi)})` : ''}`, ...(r.note ? [r.note] : [])]}>
                  <text x={left - 10} y={cy + 4} textAnchor="end" className="cw-row-label">{narrow ? r.id : r.label}</text>
                  <rect x={left} y={cy - rowH / 2} width={width - left - right} height={rowH} fill="transparent" />
                  {ci && <line x1={x(r.lo)} x2={x(r.hi)} y1={cy} y2={cy} stroke={color} strokeWidth="2" strokeLinecap="round" />}
                  {r.group === 'closed'
                    ? <circle cx={x(r.value)} cy={cy} r="5.5" fill={color} className="cw-ring" />
                    : <rect x={x(r.value) - 5} y={cy - 5} width="10" height="10" rx="2" fill={color} className="cw-ring" />}
                </Mark>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Scatter of quality against a cost measure, with 95% intervals on quality and short direct labels.
 * points: [{ id, label, x, y, lo, hi, group }]
 */
export function Frontier({ points, xLabel, yLabel, xFmt = fmtTick, yDomain, ...frame }) {
  const valid = points.filter((p) => p.x != null && p.y != null);
  const height = 260;
  return (
    <ChartFrame {...frame} height={height} unavailable={frame.unavailable || (valid.length < 2 && 'Needs at least two configurations with both measures.')}>
      {({ width, showTip, hideTip }) => {
        const left = 58, right = 18, top = 12, bottom = 46;
        const xs = valid.map((p) => p.x);
        const ylo = yDomain?.[0] ?? Math.max(0, Math.min(...valid.map((p) => p.lo ?? p.y)) - 0.05);
        const yhi = yDomain?.[1] ?? Math.min(1, Math.max(...valid.map((p) => p.hi ?? p.y)) + 0.05);
        const pad = (Math.max(...xs) - Math.min(...xs)) * 0.08 || 1;
        const x0 = Math.max(0, Math.min(...xs) - pad), x1 = Math.max(...xs) + pad;
        const x = scale(x0, x1, left, width - right);
        const y = scale(ylo, yhi, height - bottom, top);
        // Direct labels: place right of the point, nudged down when they would overlap an earlier label.
        const placed = [];
        const labels = [...valid].sort((a, b) => x(a.x) - x(b.x) || y(a.y) - y(b.y)).map((p) => {
          let ly = y(p.y) - 8;
          const lx = x(p.x) + 8;
          const w = p.id.length * 6.5;
          while (placed.some((q) => Math.abs(q.x - lx) < Math.max(w, q.w) && Math.abs(q.y - ly) < 12)) ly += 12;
          placed.push({ x: lx, y: ly, w });
          return { id: p.id, x: Math.min(lx, width - right - w), y: ly };
        });
        return (
          <svg width={width} height={height} className="cw-svg">
            <g className="cw-axis" aria-hidden="true">
              {ticks(ylo, yhi, 4).map((t) => (
                <g key={t}><line x1={left} x2={width - right} y1={y(t)} y2={y(t)} className="cw-grid" />
                  <text x={left - 8} y={y(t) + 4} textAnchor="end">{t.toFixed(2)}</text></g>
              ))}
              {ticks(x0, x1, width < 480 ? 3 : 5).map((t) => <text key={t} x={x(t)} y={height - bottom + 16} textAnchor="middle">{xFmt(t)}</text>)}
              <text x={left + (width - left - right) / 2} y={height - 8} textAnchor="middle" className="cw-axis-title">{xLabel}</text>
              <text transform={`translate(12 ${top + (height - top - bottom) / 2}) rotate(-90)`} textAnchor="middle" className="cw-axis-title">{yLabel}</text>
            </g>
            {valid.map((p) => {
              const color = p.group === 'closed' ? 'var(--chart-primary)' : 'var(--chart-neutral)';
              return (
                <Mark key={p.id} showTip={showTip} hideTip={hideTip} x={x(p.x)} y={y(p.y)}
                  label={`${p.label}: ${yLabel} ${p.y.toFixed(3)}, ${xLabel} ${xFmt(p.x)}`}
                  tip={[p.label, `${yLabel}: ${p.y.toFixed(3)}${p.lo != null ? ` (95% CI ${p.lo.toFixed(3)}–${p.hi.toFixed(3)})` : ''}`, `${xLabel}: ${xFmt(p.x)}`]}>
                  <circle cx={x(p.x)} cy={y(p.y)} r="14" fill="transparent" />
                  {p.lo != null && <line x1={x(p.x)} x2={x(p.x)} y1={y(p.lo)} y2={y(p.hi)} stroke={color} strokeWidth="2" strokeLinecap="round" opacity="0.55" />}
                  {p.group === 'closed'
                    ? <circle cx={x(p.x)} cy={y(p.y)} r="5.5" fill={color} className="cw-ring" />
                    : <rect x={x(p.x) - 5} y={y(p.y) - 5} width="10" height="10" rx="2" fill={color} className="cw-ring" />}
                </Mark>
              );
            })}
            <g aria-hidden="true">{labels.map((l) => <text key={l.id} x={l.x} y={l.y} className="cw-point-label">{l.id}</text>)}</g>
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Forest plot of paired differences with 95% intervals and a zero line.
 * rows: [{ id, label, diff, lo, hi, p, pAdj }]
 */
export function ForestPlot({ rows, xLabel, ...frame }) {
  const valid = rows.filter((r) => r.diff != null && r.lo != null && r.hi != null);
  const rowH = 36;
  const height = valid.length * rowH + 52;
  const pFmt = (v) => (v == null ? '—' : v < 0.001 ? '<0.001' : v.toFixed(3));
  return (
    <ChartFrame {...frame} height={height} unavailable={frame.unavailable || (!valid.length && 'No paired comparison with an interval in this experiment.')}>
      {({ width, showTip, hideTip }) => {
        const narrow = width < 520;
        const left = narrow ? 64 : 160;
        const right = narrow ? 16 : 150;
        const ext = Math.max(0.05, ...valid.flatMap((r) => [Math.abs(r.lo), Math.abs(r.hi)])) * 1.1;
        const x = scale(-ext, ext, left, width - right);
        const plotBottom = valid.length * rowH + 6;
        const pct = (v) => `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}`;
        return (
          <svg width={width} height={height} className="cw-svg">
            <AxisX x={x} ticksV={ticks(-ext, ext, narrow ? 4 : 6)} y={plotBottom} top={0} fmt={(v) => pct(v)} label={xLabel} width={width - right} left={left} />
            <line x1={x(0)} x2={x(0)} y1={0} y2={plotBottom} className="cw-zero-line" />
            {!narrow && <text x={width - right + 12} y={-2} className="cw-axis" dy="10" aria-hidden="true"><tspan className="cw-axis-title">p · Holm p</tspan></text>}
            {valid.map((r, i) => {
              const cy = i * rowH + rowH / 2 + 8;
              const color = r.hi < 0 || r.lo > 0 ? 'var(--chart-primary)' : 'var(--chart-neutral)';
              return (
                <Mark key={r.id} showTip={showTip} hideTip={hideTip} x={x(r.diff)} y={cy}
                  label={`${r.label}: difference ${pct(r.diff)} points, 95% interval ${pct(r.lo)} to ${pct(r.hi)}, p ${pFmt(r.p)}, Holm-adjusted p ${pFmt(r.pAdj)}`}
                  tip={[r.label, `Difference ${pct(r.diff)} pts (95% CI ${pct(r.lo)} to ${pct(r.hi)})`, `p ${pFmt(r.p)} · Holm p ${pFmt(r.pAdj)}`]}>
                  <text x={left - 10} y={cy + 4} textAnchor="end" className="cw-row-label">{narrow ? r.id : r.label}</text>
                  <rect x={left} y={cy - rowH / 2} width={width - left - right} height={rowH} fill="transparent" />
                  <line x1={x(r.lo)} x2={x(r.hi)} y1={cy} y2={cy} stroke={color} strokeWidth="2" strokeLinecap="round" />
                  <rect x={x(r.diff) - 5} y={cy - 5} width="10" height="10" rx="2" fill={color} className="cw-ring" />
                  {!narrow && <text x={width - right + 12} y={cy + 4} className="cw-row-label cw-num">{pFmt(r.p)} · {pFmt(r.pAdj)}</text>}
                </Mark>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Diverging bars: answers a revision fixed (right) against answers it broke (left).
 * rows: [{ id, label, fixed, broken, p }]
 */
export function DivergingBars({ rows, ...frame }) {
  const valid = rows.filter((r) => r.fixed != null && r.broken != null);
  const rowH = 36;
  const height = valid.length * rowH + 28;
  return (
    <ChartFrame {...frame} height={height} unavailable={frame.unavailable || (!valid.length && 'This experiment has no closed-loop runs.')}
      legend={<><LegendItem shape="square" color="var(--chart-primary)">Fixed (wrong → right)</LegendItem><LegendItem shape="square" color="var(--chart-warm)">Broken (right → wrong)</LegendItem></>}>
      {({ width, showTip, hideTip }) => {
        const narrow = width < 480;
        const left = narrow ? 64 : 170;
        const right = 34;
        const max = Math.max(1, ...valid.flatMap((r) => [r.fixed, r.broken]));
        const mid = left + (width - left - right) / 2;
        const half = (width - left - right) / 2 - 30;  // room for the value label at the end of the longest bar
        const w = (v) => (v / max) * half;
        const plotBottom = valid.length * rowH;
        return (
          <svg width={width} height={height} className="cw-svg">
            <line x1={mid} x2={mid} y1={0} y2={plotBottom} className="cw-zero-line" />
            <g className="cw-axis" aria-hidden="true">
              <text x={mid - 6} y={plotBottom + 18} textAnchor="end">← broken</text>
              <text x={mid + 6} y={plotBottom + 18}>fixed →</text>
            </g>
            {valid.map((r, i) => {
              const cy = i * rowH + rowH / 2;
              const net = r.fixed - r.broken;
              return (
                <Mark key={r.id} showTip={showTip} hideTip={hideTip} x={mid} y={cy}
                  label={`${r.label}: revision fixed ${r.fixed} answers and broke ${r.broken}${r.p != null ? `, sign test p ${r.p.toFixed(3)} (unadjusted)` : ''}`}
                  tip={[r.label, `Fixed ${r.fixed} · broken ${r.broken} · net ${net > 0 ? '+' : ''}${net}`, ...(r.p != null ? [`Sign test p ${r.p.toFixed(3)} (unadjusted)`] : [])]}>
                  <text x={left - 10} y={cy + 4} textAnchor="end" className="cw-row-label">{narrow ? r.id : r.label}</text>
                  <rect x={left} y={cy - rowH / 2} width={width - left - right} height={rowH} fill="transparent" />
                  <rect x={mid - w(r.broken) - 1} y={cy - 8} width={Math.max(0, w(r.broken))} height="16" rx="4" fill="var(--chart-warm)" />
                  <rect x={mid + 1} y={cy - 8} width={Math.max(0, w(r.fixed))} height="16" rx="4" fill="var(--chart-primary)" />
                  <text x={mid - w(r.broken) - 6} y={cy + 4} textAnchor="end" className="cw-value-label cw-num">{r.broken}</text>
                  <text x={mid + w(r.fixed) + 6} y={cy + 4} className="cw-value-label cw-num">{r.fixed}</text>
                </Mark>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Small multiples: one horizontal bar chart per measure, sharing the configuration order.
 * metrics: [{ key, title, fmt, values: [{ id, label, value, group }] }]
 */
export function SmallMultiples({ metrics, ...frame }) {
  const anyData = metrics.some((m) => m.values.some((v) => v.value != null));
  const n = metrics[0]?.values.length || 0;
  const height = n * 26 + 34;
  return (
    <ChartFrame {...frame} height={height} unavailable={frame.unavailable || (!anyData && 'No overhead measurements in this experiment.')}>
      {({ width, showTip, hideTip }) => {
        const cols = width < 640 ? 1 : metrics.length;
        const gap = 24;
        const cellW = (width - gap * (cols - 1)) / cols;
        const rowsOfCells = Math.ceil(metrics.length / cols);
        const cellH = n * 26 + 34;
        return (
          <svg width={width} height={cellH * rowsOfCells} className="cw-svg">
            {metrics.map((m, mi) => {
              const ox = (mi % cols) * (cellW + gap);
              const oy = Math.floor(mi / cols) * cellH;
              const label = 56;
              const max = Math.max(...m.values.map((v) => v.value ?? 0)) || 1;
              const bw = (v) => (v / max) * (cellW - label - 52);
              return (
                <g key={m.key} transform={`translate(${ox} ${oy})`}>
                  <text x={0} y={14} className="cw-axis-title">{m.title}</text>
                  {m.values.map((v, i) => {
                    const cy = 32 + i * 26;
                    const color = v.group === 'closed' ? 'var(--chart-primary)' : 'var(--chart-neutral)';
                    return (
                      <Mark key={v.id} showTip={showTip} hideTip={hideTip} x={ox + label} y={oy + cy}
                        label={`${m.title}, ${v.label}: ${v.value == null ? 'not measured' : m.fmt(v.value)}`}
                        tip={[v.label, `${m.title}: ${v.value == null ? 'not measured' : m.fmt(v.value)}`]}>
                        <text x={label - 8} y={cy + 4} textAnchor="end" className="cw-row-label">{v.id}</text>
                        <rect x={label} y={cy - 11} width={cellW - label} height={22} fill="transparent" />
                        {v.value == null
                          ? <text x={label} y={cy + 4} className="cw-muted-label">not measured</text>
                          : <><rect x={label} y={cy - 7} width={Math.max(2, bw(v.value))} height="14" rx="4" fill={color} />
                            <text x={label + Math.max(2, bw(v.value)) + 6} y={cy + 4} className="cw-value-label cw-num">{m.fmt(v.value)}</text></>}
                      </Mark>
                    );
                  })}
                </g>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Original, theme-aware diagram of the agent pipeline (no external imagery). Agents active at the selected level are
 * drawn solid; the rest are dimmed. Nodes are buttons (Enter/Space) that select an agent. Narrow screens stack it.
 */
const PIPE = {
  research: 'Research Agent', diagnosis: 'Diagnosis Agent', verifier: 'Verifier Agent', safety: 'Safety Validator',
  consistency: 'Consistency Checker', attending: 'HITL Simulator', report: 'Report Agent',
};
const PIPE_LABEL = {
  research: ['Research', 'extract findings'], diagnosis: ['Diagnosis', 'ranked differential'], verifier: ['Verifier', 'grounding'],
  safety: ['Safety', 'validator'], consistency: ['Consistency', 'checker'], attending: ['Attending', 'simulated reviewer'],
  report: ['Report', 'SOAP note'],
};

export function PipelineDiagram({ active, selected, onSelect, title, subtitle }) {
  return (
    <ChartFrame title={title} subtitle={subtitle} height={252} summary={`Active agents: ${active.join(', ')}`}>
      {({ width }) => {
        const narrow = width < 640;
        const W = narrow ? width : Math.max(width, 640);
        // Column layout: case → research → diagnosis → three parallel checks → attending → report.
        const nw = narrow ? Math.min(118, W * 0.3) : Math.min(124, W * 0.135);
        // Six columns inset by half a node, so the first and last nodes are never clipped.
        const cols = narrow ? null : [0, 0.19, 0.38, 0.6, 0.8, 1].map((f) => nw / 2 + 2 + f * (W - nw - 4));
        const pos = narrow ? {
          case: [W / 2, 18], research: [W / 2, 74], diagnosis: [W / 2, 138],
          verifier: [W * 0.18, 214], safety: [W / 2, 214], consistency: [W * 0.82, 214],
          attending: [W / 2, 290], report: [W / 2, 354],
        } : {
          case: [cols[0], 110], research: [cols[1], 110], diagnosis: [cols[2], 110],
          verifier: [cols[3], 42], safety: [cols[3], 110], consistency: [cols[3], 178],
          attending: [cols[4], 110], report: [cols[5], 110],
        };
        const H = narrow ? 384 : 252;
        const nh = 44;
        const on = (k) => k === 'case' || active.includes(PIPE[k]);
        const edge = (a, b) => {
          const [x1, y1] = pos[a]; const [x2, y2] = pos[b];
          const dim = !(on(a) && on(b));
          return narrow
            ? <path key={`${a}-${b}`} d={`M${x1} ${y1 + nh / 2} C${x1} ${(y1 + y2) / 2} ${x2} ${(y1 + y2) / 2} ${x2} ${y2 - nh / 2}`} className={`cw-edge${dim ? ' dim' : ''}`} />
            : <path key={`${a}-${b}`} d={`M${x1 + nw / 2} ${y1} C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2 - nw / 2} ${y2}`} className={`cw-edge${dim ? ' dim' : ''}`} />;
        };
        const checks = ['verifier', 'safety', 'consistency'];
        const node = (k) => {
          const [cx, cy] = pos[k];
          const isOn = on(k);
          const agent = PIPE[k];
          const [l1, l2] = k === 'case' ? ['Case text', 'question only'] : PIPE_LABEL[k];
          const interactive = k !== 'case';
          const press = () => interactive && onSelect?.(agent);
          return (
            <g key={k} transform={`translate(${cx - nw / 2} ${cy - nh / 2})`}
              className={`cw-node${isOn ? '' : ' dim'}${selected === agent ? ' selected' : ''}${interactive ? ' interactive' : ''}`}
              {...(interactive ? { role: 'button', tabIndex: 0, 'aria-pressed': selected === agent,
                'aria-label': `${l1} ${l2}${isOn ? '' : ' (not run at this level)'}`, onClick: press,
                onKeyDown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); press(); } } } : { 'aria-hidden': true })}>
              <rect width={nw} height={nh} rx="10" />
              <text x={nw / 2} y={19} textAnchor="middle" className="cw-node-title">{l1}</text>
              <text x={nw / 2} y={33} textAnchor="middle" className="cw-node-sub">{l2}</text>
            </g>
          );
        };
        const anyCheck = checks.some(on) || on('attending');
        return (
          <div style={{ overflowX: narrow ? 'visible' : 'auto' }}>
            <svg width={W} height={H} className="cw-svg cw-diagram">
              {edge('case', 'research')}{edge('research', 'diagnosis')}
              {checks.map((c) => edge('diagnosis', c))}
              {checks.map((c) => edge(c, 'attending'))}
              {edge('attending', 'report')}
              {!narrow && anyCheck && (
                <g aria-hidden="true">
                  {/* Routed below the parallel checks: down, across under the consistency checker, and back up. */}
                  <path d={`M${pos.attending[0]} ${pos.attending[1] + nh / 2} L${pos.attending[0]} ${H - 26} Q${pos.attending[0]} ${H - 16} ${pos.attending[0] - 10} ${H - 16} L${pos.diagnosis[0] + 10} ${H - 16} Q${pos.diagnosis[0]} ${H - 16} ${pos.diagnosis[0]} ${H - 26} L${pos.diagnosis[0]} ${pos.diagnosis[1] + nh / 2}`} className="cw-edge loop" />
                  <text x={(pos.attending[0] + pos.diagnosis[0]) / 2} y={H - 2} textAnchor="middle" className="cw-node-sub">closed loop: one bounded revision</text>
                </g>
              )}
              {Object.keys(pos).map(node)}
            </svg>
          </div>
        );
      }}
    </ChartFrame>
  );
}
