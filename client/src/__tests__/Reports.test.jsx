// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import Reports from '../pages/Reports';
import { setExperiment } from '../lib/api';

afterEach(cleanup);

function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k), clear: () => m.clear() };
}

describe('Reports & Reproducibility', () => {
  let calls;
  beforeEach(() => {
    const storage = memoryStorage();
    Object.defineProperty(window, 'localStorage', { value: storage, configurable: true });
    vi.stubGlobal('localStorage', storage);
    calls = [];
    global.fetch = vi.fn(async (url) => {
      calls.push(String(url));
      if (String(url).startsWith('/api/reports/csv')) return { ok: true, status: 200, blob: async () => new Blob(['id\n1']) };
      if (String(url).startsWith('/api/reports/latex')) return { ok: true, status: 200, text: async () => '\\begin{table}' };
      return { ok: true, status: 200, json: async () => ({ n_runs_analyzed: 1800, n_cases: 300, models: ['m'], variants: [] }) };
    });
    URL.createObjectURL = vi.fn(() => 'blob:x');
    URL.revokeObjectURL = vi.fn();
  });

  it('exports and shows the experiment selected in the top bar', async () => {
    act(() => setExperiment('medqa_paired'));
    render(<Reports />);
    await waitFor(() => expect(calls).toContain('/api/reports/latex?experiment=medqa_paired'));
    expect(calls).toContain('/api/research/findings?experiment=medqa_paired');
    fireEvent.click(screen.getByRole('button', { name: /Download this experiment's runs/ }));
    await waitFor(() => expect(calls).toContain('/api/reports/csv?experiment=medqa_paired'));
    expect(screen.getByText('1800 runs, 300 cases')).toBeTruthy();
  });

  it('shows a distinct error when the export fails', async () => {
    global.fetch = vi.fn(async (url) => (String(url).startsWith('/api/reports/csv')
      ? { ok: false, status: 503, blob: async () => new Blob() }
      : { ok: true, status: 200, text: async () => '', json: async () => ({}) }));
    render(<Reports />);
    fireEvent.click(screen.getByRole('button', { name: /Download this experiment's runs/ }));
    expect(await screen.findByText('Export failed')).toBeTruthy();
    expect(screen.getByText(/CSV export unavailable \(503\)/)).toBeTruthy();
  });
});
