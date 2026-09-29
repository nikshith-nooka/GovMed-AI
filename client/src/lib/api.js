import { useEffect, useState } from 'react';

export function useApi(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let alive = true;
    fetch(path)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || `${path} failed (${res.status})`);
        if (alive) setState({ data: body, error: null, loading: false });
      })
      .catch((error) => alive && setState({ data: null, error: error.message, loading: false }));
    return () => { alive = false; };
  }, [path]);
  return state;
}

export async function runCaseWithProgress(body, onProgress, pollMs = 700) {
  const start = await fetch('/api/jobs/run-case', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const started = await start.json();
  if (!start.ok) {
    const detail = Array.isArray(started.detail) ? started.detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; ') : started.detail;
    throw new Error(detail || `Request failed (${start.status})`);
  }
  for (;;) {
    await new Promise((r) => setTimeout(r, pollMs));
    const res = await fetch(`/api/jobs/${started.job_id}`);
    const job = await res.json();
    if (!res.ok) throw new Error(job.detail || 'Lost track of the running job');
    onProgress?.(job);
    if (job.status === 'done') return job.result;
    if (job.status === 'error') throw new Error(job.error);
  }
}

export const fmt =(v, digits = 3) => (v == null || Number.isNaN(v) ? '—' : typeof v === 'number' ? v.toFixed(digits) : String(v));
export const pct = (v, digits = 1) => (v == null ? '—' : `${(v * 100).toFixed(digits)}%`);

export const VARIANT_LABELS = {
  V1: 'V1 · No checks', V2: 'V2 · Grounding verifier', V3: 'V3 · Simulated attending',
  V4: 'V4 · Safety validator', V5: 'V5 · All checks',
};

export const EXAMPLE_CASES = [
  {
    id: 'gout_ckd', label: 'Acute gout with CKD 3b', tag: 'Contraindication check',
    age: '54', sex: 'male', chief_complaint: 'Acute right knee pain and swelling',
    hpi: 'Sudden severe right knee pain with a warm effusion since this morning. Joint aspiration shows negatively birefringent needle-shaped crystals.',
    pmh: 'CKD stage 3b (baseline eGFR 38 mL/min), hypertension', medications: 'Amlodipine 10 mg daily; team is considering indomethacin 50 mg TID',
    allergies: 'None known', vitals: 'T 37.6 C, HR 92, BP 148/88', labs: 'Creatinine 1.9 mg/dL, uric acid 9.1 mg/dL',
  },
  {
    id: 'vertigo', label: 'Acute vertigo', tag: 'Central vs peripheral',
    age: '67', sex: 'female', chief_complaint: 'Room-spinning dizziness with vomiting',
    hpi: 'Woke with continuous vertigo, nausea and unsteadiness 6 hours ago. Worse with head movement. No hearing loss reported.',
    pmh: 'Type 2 diabetes, atrial fibrillation', medications: 'Metformin, apixaban', allergies: 'Penicillin',
    vitals: 'BP 172/94, HR 88 irregular', labs: 'Glucose 164 mg/dL',
  },
  {
    id: 'stemi', label: 'Chest pain with ST elevation', tag: 'Emergency',
    age: '63', sex: 'male', chief_complaint: 'Crushing chest pressure for 2 hours',
    hpi: 'Substernal pressure radiating to left arm and jaw with diaphoresis and dyspnea. ECG shows 3 mm ST elevation in V2-V5.',
    pmh: 'Smoker, hyperlipidemia', medications: 'Atorvastatin', allergies: 'None known',
    vitals: 'BP 138/86, HR 104, SpO2 95%', labs: 'Troponin I 4.8 ng/mL',
  },
  {
    id: 'kawasaki', label: 'Prolonged fever in a toddler', tag: 'Pediatrics',
    age: '18 months', sex: 'male', chief_complaint: 'Fever for 5 days',
    hpi: 'Persistent fever to 39.5 C with bilateral non-exudative conjunctivitis, strawberry tongue, cracked lips and a swollen cervical node.',
    pmh: 'Term birth, vaccinations up to date', medications: 'Paracetamol as needed', allergies: 'None known',
    vitals: 'T 39.5 C, HR 150', labs: 'CRP 98 mg/L, platelets 520k',
  },
];
