import { useEffect, useState } from 'react';

// ---------------------------------------------------------------- API token (optional server auth)
const TOKEN_KEY = 'govbench.apiToken';
export const AUTH_EVENT = 'govbench:auth-required';
export const TOKEN_CHANGED_EVENT = 'govbench:token-changed';

export function getApiToken() {
  try { return window.localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; }
}

export function setApiToken(token) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage blocked: token lasts for this page only */ }
}

/** fetch() with the stored bearer token; a 401 asks the app to show the token dialog. */
export async function apiFetch(path, options = {}) {
  const token = getApiToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: { path, hadToken: !!token } }));
  return res;
}

export function postJson(path, body, options = {}) {
  return apiFetch(path, { ...options, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

/** Error raised when the server finds possible patient identifiers (HTTP 422, code phi_detected). */
export class PhiDetectedError extends Error {
  constructor(detail) {
    super(detail.message || 'Possible patient identifiers detected.');
    this.name = 'PhiDetectedError';
    this.types = detail.types || [];
  }
}

export function errorFromBody(body, status) {
  const detail = body?.detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.code === 'phi_detected') return new PhiDetectedError(detail);
  if (Array.isArray(detail)) return new Error(detail.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('; '));
  if (status === 401) return new Error('This server requires an API token. Add it from the key icon in the top bar.');
  return new Error((typeof detail === 'string' && detail) || `Request failed (${status})`);
}

/** Re-renders when the API token changes, so data hooks refetch with the new credentials. */
export function useTokenVersion() {
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const bump = () => setVersion((v) => v + 1);
    window.addEventListener(TOKEN_CHANGED_EVENT, bump);
    return () => window.removeEventListener(TOKEN_CHANGED_EVENT, bump);
  }, []);
  return version;
}

export function useApi(path) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const tokenVersion = useTokenVersion();
  useEffect(() => {
    let alive = true;
    apiFetch(path)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw errorFromBody(body, res.status);
        if (alive) setState({ data: body, error: null, loading: false });
      })
      .catch((error) => alive && setState({ data: null, error: error.message, loading: false }));
    return () => { alive = false; };
  }, [path, tokenVersion]);
  return state;
}

export async function runCaseWithProgress(body, onProgress, { signal, pollMs = 700, timeoutMs = 10 * 60 * 1000 } = {}) {
  const start = await postJson('/api/jobs/run-case', body);
  const started = await start.json().catch(() => ({}));
  if (!start.ok) throw errorFromBody(started, start.status);
  const deadline = Date.now() + timeoutMs;
  for (;;) {
    await new Promise((r) => setTimeout(r, pollMs));
    if (signal?.aborted) throw new DOMException('Cancelled', 'AbortError');
    if (Date.now() > deadline) throw new Error('The run took longer than 10 minutes and was abandoned.');
    const res = await apiFetch(`/api/jobs/${started.job_id}`);
    const job = await res.json().catch(() => ({}));
    if (!res.ok) throw res.status === 404 ? new Error('Lost track of the running job') : errorFromBody(job, res.status);
    onProgress?.(job);
    if (job.status === 'done') return job.result;
    if (job.status === 'error') throw new Error(typeof job.error === 'string' ? job.error : JSON.stringify(job.error));
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
