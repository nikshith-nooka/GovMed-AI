// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { DEFAULT_EXPERIMENT, findingsPath, getExperiment, setExperiment, useExperiment } from '../lib/api';
import TopNavbar from '../components/TopNavbar';

afterEach(cleanup);

const LISTING = {
  default: 'open150',
  experiments: [
    { key: 'open150', label: '150 mixed cases · open loop', status: 'first experiment', available: true },
    { key: 'medqa_paired', label: '300 MedQA · paired closed loop', status: 'reported in the paper', available: true },
    { key: 'missing', label: 'Not analysed yet', status: '', available: false },
  ],
};

function Probe() {
  return <span data-testid="exp">{useExperiment()}</span>;
}

// Node 26 ships an experimental global localStorage that hides jsdom's; use a plain in-memory store.
function memoryStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k), clear: () => m.clear() };
}

describe('selected experiment', () => {
  beforeEach(() => {
    const storage = memoryStorage();
    Object.defineProperty(window, 'localStorage', { value: storage, configurable: true });
    vi.stubGlobal('localStorage', storage);
    global.fetch = vi.fn(async (url) => ({
      ok: true, status: 200,
      json: async () => (String(url).includes('/api/research/experiments') ? LISTING : {}),
    }));
  });

  it('defaults to the 150-case experiment and builds an encoded findings URL', () => {
    expect(getExperiment()).toBe(DEFAULT_EXPERIMENT);
    expect(findingsPath('medqa_paired')).toBe('/api/research/findings?experiment=medqa_paired');
    expect(findingsPath('a b')).toBe('/api/research/findings?experiment=a%20b');
  });

  it('shares the selection across components and remembers it', () => {
    render(<Probe />);
    expect(screen.getByTestId('exp').textContent).toBe('open150');
    act(() => setExperiment('medqa_paired'));
    expect(screen.getByTestId('exp').textContent).toBe('medqa_paired');
    expect(window.localStorage.getItem('govbench.experiment')).toBe('medqa_paired');
  });

  it('the top-bar picker lists only available experiments and changes the selection', async () => {
    render(<TopNavbar />);
    const picker = await screen.findByLabelText('Experiment shown on results pages');
    await waitFor(() => expect(picker.querySelectorAll('option').length).toBe(2));
    expect([...picker.querySelectorAll('option')].map((o) => o.textContent)).not.toContain('Not analysed yet');
    fireEvent.change(picker, { target: { value: 'medqa_paired' } });
    expect(getExperiment()).toBe('medqa_paired');
  });
});
