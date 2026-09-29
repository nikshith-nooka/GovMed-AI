import React, { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff, KeyRound, X } from 'lucide-react';
import '../pages/clinical.css';
import { getApiToken, setApiToken, TOKEN_CHANGED_EVENT } from '../lib/api';

// Mounted only while open, so state starts fresh from the stored token each time.
export default function ApiTokenDialog({ onClose, authRequired, reason }) {
  const [value, setValue] = useState(getApiToken);
  const [show, setShow] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => { clearTimeout(t); window.removeEventListener('keydown', onKey); };
  }, [onClose]);

  const save = (token) => {
    setApiToken(token.trim());
    window.dispatchEvent(new CustomEvent(TOKEN_CHANGED_EVENT));
    onClose();
  };

  return (
    <div className="cw-modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <form className="cw-modal" role="dialog" aria-modal="true" aria-labelledby="cw-token-title"
        onSubmit={(e) => { e.preventDefault(); save(value); }}>
        <div className="cw-modal-head">
          <h3 id="cw-token-title"><KeyRound size={15} /> API token</h3>
          <button type="button" className="cw-icon-btn" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        {reason === 'unauthorized' && (
          <div className="cw-banner error" style={{ marginBottom: 12 }}>
            <div><strong>The server rejected the request</strong>Enter the token set in GOVBENCH_API_TOKEN on the server.</div>
          </div>
        )}
        <p className="cw-muted" style={{ marginTop: 0 }}>
          {authRequired
            ? 'This server requires a bearer token for running cases, jobs, experiments and reviews.'
            : 'This server does not currently require a token. You only need one if an administrator set GOVBENCH_API_TOKEN.'}
        </p>
        <label className="cw-label" htmlFor="cw-token">Token</label>
        <div className="cw-input-group">
          <input id="cw-token" ref={inputRef} className="cw-input" type={show ? 'text' : 'password'} autoComplete="off"
            spellCheck={false} value={value} onChange={(e) => setValue(e.target.value)} placeholder="Paste token" />
          <button type="button" className="cw-icon-btn" onClick={() => setShow((s) => !s)} aria-label={show ? 'Hide token' : 'Show token'}>
            {show ? <EyeOff size={15} /> : <Eye size={15} />}
          </button>
        </div>
        <p className="cw-muted">Stored only in this browser (localStorage) and sent as an Authorization header to this server.</p>
        <div className="cw-modal-actions">
          {getApiToken() && <button type="button" className="cw-btn ghost small" onClick={() => save('')}>Remove token</button>}
          <span style={{ flex: 1 }} />
          <button type="button" className="cw-btn ghost small" onClick={onClose}>Cancel</button>
          <button type="submit" className="cw-btn small" disabled={!value.trim()}>Save token</button>
        </div>
      </form>
    </div>
  );
}
