// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DivergingBars, DotPlotCI, ForestPlot, Frontier, PipelineDiagram, SmallMultiples } from '../components/charts';
import { wilson, accuracyRows, forestRows, frontierPoints, overheadMetrics, revisionRows } from '../lib/research';

afterEach(cleanup);

// A small report shaped like /api/research/findings (synthetic numbers, not study results).
const REPORT = {
  measurement_validity: { cases_with_valid_gold: 100, cases_total: 100, cases_with_answer_key: 100 },
  variants: [
    { variant_id: 'V1', accuracy_valid_gold: 0.5, tokens_mean: 2000, e2e_latency_p50_s: 20, model_calls_mean: 2, governance_latency_p50_s: 0 },
    { variant_id: 'V5-CL', accuracy_valid_gold: 0.4, tokens_mean: 9000, e2e_latency_p50_s: 90, model_calls_mean: 8, governance_latency_p50_s: null },
  ],
  accuracy_tests: [{ comparison: 'V5-CL - V1', accuracy_diff: -0.1, accuracy_diff_ci95_low: -0.18, accuracy_diff_ci95_high: -0.02, mcnemar_exact_p: 0.01, mcnemar_exact_p_holm: 0.4 }],
  revision_by_variant: [{ variant_id: 'V5-CL', within_run_fixed: 7, within_run_broken: 12, sign_test_p: 0.36 }],
};

describe('statistics used by the charts', () => {
  it('Wilson interval matches a hand calculation', () => {
    // p = 0.5, n = 100: centre 0.5, half-width 1.96*sqrt(0.25/100 + 1.96^2/40000)/(1 + 1.96^2/100) = 0.0961
    const [lo, hi] = wilson(0.5, 100);
    expect(lo).toBeCloseTo(0.4038, 3);
    expect(hi).toBeCloseTo(0.5962, 3);
    expect(wilson(null, 100)).toEqual([null, null]);
    expect(wilson(0.5, 0)).toEqual([null, null]);
  });
});

describe('report adapters', () => {
  it('derive every chart row from the report and never fill in missing values', () => {
    const rows = accuracyRows(REPORT);
    expect(rows.map((r) => [r.id, r.group, r.value])).toEqual([['V1', 'open', 0.5], ['V5-CL', 'closed', 0.4]]);
    expect(rows[0].lo).toBeCloseTo(0.4038, 3);
    expect(frontierPoints(REPORT, 'tokens_mean').map((p) => p.x)).toEqual([2000, 9000]);
    expect(forestRows(REPORT)[0]).toMatchObject({ id: 'V5-CL', diff: -0.1, p: 0.01, pAdj: 0.4 });
    expect(revisionRows(REPORT)[0]).toMatchObject({ id: 'V5-CL', fixed: 7, broken: 12 });
    const gov = overheadMetrics(REPORT).find((m) => m.key === 'gov');
    expect(gov.values.map((v) => v.value)).toEqual([0, null]);     // null stays null, not 0
  });
});

describe('chart components', () => {
  it('dot plot gives each configuration a focusable, labelled mark with its interval', () => {
    render(<DotPlotCI rows={accuracyRows(REPORT)} title="Accuracy" summary="s" xLabel="Accuracy" />);
    const mark = screen.getByRole('img', { name: /V1 · No checks: 0.500, 95% interval 0.404 to 0.596/ });
    expect(mark.getAttribute('tabindex')).toBe('0');
    fireEvent.focus(mark);
    expect(screen.getByRole('tooltip').textContent).toContain('95% CI 0.404–0.596');
  });

  it('every chart shows an unavailable state instead of drawing empty or invented data', () => {
    render(<>
      <DotPlotCI rows={[]} title="a" summary="" />
      <Frontier points={[{ id: 'V1', label: 'V1', x: 1, y: 0.5 }]} title="b" summary="" />
      <ForestPlot rows={[]} title="c" summary="" />
      <DivergingBars rows={[]} title="d" summary="" />
      <SmallMultiples metrics={[{ key: 'k', title: 't', fmt: String, values: [{ id: 'V1', value: null }] }]} title="e" summary="" />
    </>);
    expect(screen.getAllByRole('status')).toHaveLength(5);
    expect(document.querySelector('svg.cw-svg')).toBeNull();
  });

  it('forest plot labels the uncorrected and Holm-adjusted p separately', () => {
    render(<ForestPlot rows={forestRows(REPORT)} title="f" summary="" xLabel="diff" />);
    expect(screen.getByRole('img', { name: /difference -10.0 points, 95% interval -18.0 to -2.0, p 0.010, Holm-adjusted p 0.400/ })).toBeTruthy();
  });

  it('diverging bars report fixed and broken counts exactly', () => {
    render(<DivergingBars rows={revisionRows(REPORT)} title="r" summary="" />);
    expect(screen.getByRole('img', { name: /fixed 7 answers and broke 12, sign test p 0.360/ })).toBeTruthy();
  });

  it('small multiples say "not measured" for a missing value', () => {
    render(<SmallMultiples metrics={overheadMetrics(REPORT)} title="o" summary="" />);
    expect(screen.getByRole('img', { name: /Governance-only latency, median \(s\), V5-CL · All checks \(CL\): not measured/ })).toBeTruthy();
  });

  it('pipeline diagram dims agents a level does not run and selects agents by keyboard', () => {
    const picked = [];
    render(<PipelineDiagram active={['Research Agent', 'Diagnosis Agent', 'Verifier Agent']} selected="Diagnosis Agent"
      onSelect={(a) => picked.push(a)} title="G1" />);
    expect(screen.getByRole('button', { name: /Safety validator \(not run at this level\)/ })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole('button', { name: /^Verifier grounding$/ }), { key: 'Enter' });
    expect(picked).toEqual(['Verifier Agent']);
  });
});
