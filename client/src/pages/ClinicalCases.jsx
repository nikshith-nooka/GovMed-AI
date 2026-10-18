import React, { useEffect, useState } from 'react';
import './clinical.css';
import { Database, Search, Stethoscope } from 'lucide-react';

const isScorable = (c) => !!c.gold_diagnosis && !c.gold_diagnosis.toLowerCase().startsWith('clinical diagnostic note');
const DATASETS = [['All', 'All'], ['MedQA', 'MedQA'], ['PubMedQA', 'PubMedQA'], ['MedDialog', 'MedDialog']];
const inDataset = (c, key) => key === 'All' || c.id?.startsWith(key.toLowerCase());

export default function ClinicalCases({ cases = [], error = null, initialQuery = '', openInWorkspace }) {
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  useEffect(() => { setSearchQuery(initialQuery); }, [initialQuery]);
  const [dataset, setDataset] = useState('All');
  const [specialty, setSpecialty] = useState('All');
  const [activeId, setActiveId] = useState(null);

  const pool = cases || [];
  const q = searchQuery.toLowerCase();
  const inSearch = (c) => !q || [c.question, c.gold_diagnosis, c.id].some((f) => f && f.toLowerCase().includes(q));
  const filtered = pool.filter((c) => inSearch(c) && inDataset(c, dataset) && (specialty === 'All' || c.specialty === specialty));
  const specialtyCount = (s) => pool.filter((c) => inSearch(c) && inDataset(c, dataset) && (s === 'All' || c.specialty === s)).length;
  const specialties = ['All', ...Array.from(new Set(pool.map((c) => c.specialty).filter(Boolean))).sort()];
  const activeFilters = [searchQuery && `search "${searchQuery}"`, dataset !== 'All' && dataset, specialty !== 'All' && specialty].filter(Boolean);
  const clearFilters = () => { setSearchQuery(''); setDataset('All'); setSpecialty('All'); };
  const current = filtered.find((c) => c.id === activeId) || filtered[0] || null;

  return (
    <div className="cw-page">
      <div className="cw-header">
        <div>
          <div className="cw-eyebrow"><Database size={14} aria-hidden="true" /> Benchmark dataset · {pool.length} cases · {pool.filter(isScorable).length} with a real diagnosis label</div>
          <h2 className="cw-title">Case Library</h2>
          <p className="cw-sub">
            The {pool.length} cases of the mixed benchmark (MedQA, PubMedQA, MedDialog). Cases marked "not scorable" have a
            templated gold label rather than a diagnosis and are excluded from accuracy.
          </p>
        </div>
        <div className="cw-seg" role="group" aria-label="Dataset">
          {DATASETS.map(([key, label]) => (
            <button key={key} aria-pressed={dataset === key} onClick={() => setDataset(key)}>
              {label} <span className="cw-num cw-muted">{pool.filter((c) => inDataset(c, key)).length}</span>
            </button>
          ))}
        </div>
      </div>

      {error && <div className="cw-banner error" role="alert" style={{ marginBottom: 16 }}><div><strong>Could not load cases</strong>{error}</div></div>}

      <div className="cw-card" style={{ marginBottom: 16 }}>
        <div className="cw-search" style={{ marginBottom: 12 }}>
          <Search size={15} aria-hidden="true" />
          <input className="cw-input" type="search" aria-label="Search cases" placeholder="Search by diagnosis, symptoms or case ID"
            value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
        <div className="cw-chips" role="group" aria-label="Specialty">
          {specialties.map((s) => (
            <button key={s} className="cw-chip" aria-pressed={specialty === s} onClick={() => setSpecialty(s)}>
              {s} <span className="cw-num">{specialtyCount(s)}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="cases-split">
        <div className="cw-card cw-list-scroll" style={{ marginTop: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
            <h3>{filtered.length} case{filtered.length === 1 ? '' : 's'}</h3>
            {activeFilters.length > 0 && <button className="cw-link" onClick={clearFilters}>Clear filters</button>}
          </div>
          {filtered.length === 0 ? (
            <div className="cw-empty" style={{ padding: '24px 8px' }}>
              No cases match {activeFilters.join(' + ') || 'the current filters'}.
              <div style={{ marginTop: 12 }}><button className="cw-btn ghost small" onClick={clearFilters}>Clear all filters</button></div>
            </div>
          ) : (
            <div className="cw-rows">
              {filtered.map((c) => (
                <button key={c.id} className="cw-row-item" aria-current={current?.id === c.id} onClick={() => setActiveId(c.id)}>
                  <div className="head">
                    <span className="id">{c.id}</span>
                    <span style={{ display: 'flex', gap: 4 }}>
                      <span className="cw-pill pill-accent">{c.dataset ? c.dataset.split(' ')[0] : c.id?.split('_')[0]}</span>
                      {c.specialty && <span className="cw-pill">{c.specialty}</span>}
                    </span>
                  </div>
                  <div className="title">{c.gold_diagnosis || 'No gold label'}{!isScorable(c) && <span className="cw-muted"> · not scorable</span>}</div>
                  <p className="snippet">{c.question}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {current ? (
          <div className="cw-card" style={{ marginTop: 0 }}>
            <div className="cw-toolbar" style={{ marginBottom: 6 }}>
              <span className="cw-muted cw-num">{current.id}</span>
              <span className="cw-pill pill-accent">{current.dataset || current.id?.split('_')[0]}</span>
              {current.specialty && <span className="cw-pill">{current.specialty}</span>}
              {current.difficulty && <span className="cw-pill pill-warning">{current.difficulty} complexity</span>}
            </div>
            <h3 className="cw-dx" style={{ fontSize: '1.3rem' }}>
              {current.gold_diagnosis || 'No gold label'}
              {!isScorable(current) && <span className="cw-muted" style={{ fontWeight: 400 }}> (templated label, not scorable)</span>}
            </h3>
            <p className="cw-muted" style={{ marginTop: 0 }}>Gold label shown for browsing only; it is never sent to the agents.</p>

            <div className="cw-section-label" style={{ marginTop: 16 }}>Case text (what the agents receive)</div>
            <div className="cw-case-text">{current.question}</div>

            {current.recommended_plan && (<>
              <div className="cw-section-label" style={{ marginTop: 16 }}>Reference plan from the dataset</div>
              <div className="cw-case-text">{current.recommended_plan}</div>
            </>)}

            <div className="cw-section-label" style={{ marginTop: 16 }}>Dataset rationale (from the source dataset, not generated by the agents)</div>
            <div className="cw-case-text">{current.clinical_rationale || 'No rationale recorded for this case.'}</div>

            <div className="cw-toolbar" style={{ justifyContent: 'flex-end', marginTop: 18 }}>
              <button className="cw-btn" onClick={() => openInWorkspace?.({
                chief_complaint: current.question.split(/(?<=[.?!])\s/)[0].slice(0, 160),
                hpi: current.question.slice(0, 8000),
              })}>
                <Stethoscope size={16} aria-hidden="true" /> Open in Clinician Workspace
              </button>
            </div>
          </div>
        ) : (
          <div className="cw-card cw-empty" style={{ marginTop: 0 }}>{pool.length ? 'Select a case to inspect it.' : 'No cases loaded.'}</div>
        )}
      </div>
    </div>
  );
}
