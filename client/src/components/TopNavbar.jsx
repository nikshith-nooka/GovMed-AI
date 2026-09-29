import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Search, Sun, Moon, Bell, Menu, X, KeyRound } from 'lucide-react';
import ApiTokenDialog from './ApiTokenDialog';
import { apiFetch, AUTH_EVENT, getApiToken, useTokenVersion } from '../lib/api';

function readStorage(key) {
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function writeStorage(key, value) {
  try { window.localStorage.setItem(key, value); } catch { /* storage blocked */ }
}

export default function TopNavbar({ onToggleSidebar, isSidebarOpen, onSearch, onOpenReviews }) {
  const [darkMode, setDarkMode] = useState(() => {
    const stored = readStorage('govbench_theme');
    if (stored) return stored === 'dark';
    return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  });
  const [query, setQuery] = useState('');
  const [pending, setPending] = useState(null);
  const reviewer = readStorage('govbench.reviewer') || '';
  const searchRef = useRef(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [tokenDialog, setTokenDialog] = useState(null); // null | 'manual' | 'unauthorized'
  const tokenVersion = useTokenVersion();
  const hasToken = !!getApiToken();
  const closeTokenDialog = useCallback(() => setTokenDialog(null), []);

  useEffect(() => {
    apiFetch('/api/health')
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => h && setAuthRequired(!!h.auth_required))
      .catch(() => {});
    // The first 401 opens the dialog; later ones while it is open are ignored.
    const onUnauthorized = () => setTokenDialog((d) => d || 'unauthorized');
    window.addEventListener(AUTH_EVENT, onUnauthorized);
    return () => window.removeEventListener(AUTH_EVENT, onUnauthorized);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', darkMode);
    writeStorage('govbench_theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (!reviewer) return;
    apiFetch(`/api/reviews/queue?reviewer_id=${encodeURIComponent(reviewer)}&limit=1`)
      .then((r) => (r.ok ? r.json() : null))
      .then((body) => body && setPending(body.remaining))
      .catch(() => {});
  }, [reviewer, tokenVersion]);

  const submit = (e) => {
    e.preventDefault();
    onSearch?.(query.trim());
  };

  const bellTitle = reviewer
    ? `${pending ?? '…'} outputs left for ${reviewer} to review`
    : 'Open the clinician review queue';

  return (
    <header className="top-navbar">
      <div className="nav-left-group">
        <button className="mobile-menu-btn" onClick={onToggleSidebar} aria-label="Toggle navigation menu">
          {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <form className="search-bar" onSubmit={submit} role="search">
          <Search size={16} className="search-icon" />
          <input
            ref={searchRef}
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search benchmark cases by symptom, diagnosis or ID…"
            aria-label="Search benchmark cases"
          />
          <span className="cmd-k">⌘K</span>
        </form>
      </div>

      <div className="nav-right">
        <button
          className="icon-btn theme-toggle-btn"
          onClick={() => setDarkMode((prev) => !prev)}
          title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          aria-label="Toggle theme"
        >
          {darkMode ? <Sun size={18} className="theme-icon sun" /> : <Moon size={18} className="theme-icon moon" />}
        </button>
        <button
          className="icon-btn notification-btn"
          onClick={() => setTokenDialog('manual')}
          title={authRequired ? (hasToken ? 'API token set' : 'This server requires an API token') : 'API token (optional)'}
          aria-label="API token settings"
        >
          <KeyRound size={18} />
          {authRequired && !hasToken && <span className="notification-badge"></span>}
        </button>
        <button className="icon-btn notification-btn" title={bellTitle} aria-label={bellTitle} onClick={onOpenReviews}>
          <Bell size={18} />
          {pending > 0 && <span className="notification-badge"></span>}
        </button>
        <div className="user-profile" title={reviewer ? `Reviewer ID: ${reviewer}` : 'Set a reviewer ID on the Clinician Review page'}>
          <div className="avatar-circle">{(reviewer[0] || '?').toUpperCase()}</div>
          <div className="user-info">
            <div className="user-name">{reviewer || 'No reviewer ID'}</div>
            <div className="user-role">{readStorage('govbench.reviewerRole') || 'Local session'}</div>
          </div>
        </div>
      </div>
      {tokenDialog && <ApiTokenDialog reason={tokenDialog} authRequired={authRequired} onClose={closeTokenDialog} />}
    </header>
  );
}
