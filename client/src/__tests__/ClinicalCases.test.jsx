// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ClinicalCases from '../pages/ClinicalCases';

afterEach(cleanup);

// Synthetic cases (no real patient data): two datasets, two specialties, one templated (unscorable) label.
const CASES = [
  { id: 'medqa_001', specialty: 'Cardiology', gold_diagnosis: 'Myocardial infarction', question: 'Crushing chest pain for 2 hours.' },
  { id: 'medqa_002', specialty: 'Neurology', gold_diagnosis: 'Migraine', question: 'Unilateral throbbing headache.' },
  { id: 'pubmedqa_001', specialty: 'Cardiology', gold_diagnosis: 'Clinical diagnostic note for chest pain', question: 'Chest pain study abstract.' },
];

describe('Clinical Case Library', () => {
  it('counts scorable labels and lists every case', () => {
    render(<ClinicalCases cases={CASES} />);
    expect(screen.getByText(/3 cases · 2 with a real diagnosis label/)).toBeTruthy();
    expect(screen.getByRole('heading', { name: '3 cases' })).toBeTruthy();
  });

  it('filters by dataset, specialty and search, and shows a clear empty state', () => {
    render(<ClinicalCases cases={CASES} />);
    fireEvent.click(screen.getByRole('button', { name: /^MedQA/ }));
    expect(screen.getByRole('heading', { name: '2 cases' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /^Neurology/ }));
    expect(screen.getByRole('heading', { name: '1 case' })).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Search cases'), { target: { value: 'no-such-case' } });
    expect(screen.getByText(/No cases match/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear all filters' }));
    expect(screen.getByRole('heading', { name: '3 cases' })).toBeTruthy();
  });

  it('selects a case with a real button and opens it in the workspace without the gold label', () => {
    const open = vi.fn();
    render(<ClinicalCases cases={CASES} openInWorkspace={open} />);
    const row = screen.getByRole('button', { name: /medqa_002/ });
    fireEvent.click(row);
    expect(row.getAttribute('aria-current')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: /Open in Clinician Workspace/ }));
    expect(open).toHaveBeenCalledTimes(1);
    const sent = JSON.stringify(open.mock.calls[0][0]);
    expect(sent).toContain('Unilateral throbbing headache');
    expect(sent).not.toContain('Migraine');   // the gold label never travels to the pipeline
  });

  it('marks templated labels as not scorable', () => {
    render(<ClinicalCases cases={CASES} />);
    fireEvent.click(screen.getByRole('button', { name: /pubmedqa_001/ }));
    expect(screen.getByText(/templated label, not scorable/)).toBeTruthy();
  });
});
