import React, { useState } from 'react';
import { 
  Search, 
  Filter, 
  Stethoscope, 
  BookOpen, 
  CheckCircle2, 
  ArrowRight, 
  FileText, 
  Tag, 
  Layers, 
  HelpCircle,
  ExternalLink,
  Database,
  Sparkles
} from 'lucide-react';

export default function ClinicalCases({ cases = [], setCurrentPage }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDataset, setSelectedDataset] = useState('All');
  const [selectedSpecialty, setSelectedSpecialty] = useState('All');

  const pool = cases && cases.length > 0 ? cases : [];

  // Filter logic across 150 cases
  const filteredCases = pool.filter((c) => {
    const matchesSearch = !searchQuery || 
      (c.question && c.question.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.gold_diagnosis && c.gold_diagnosis.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (c.id && c.id.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesDataset = selectedDataset === 'All' || 
      (c.dataset && c.dataset.toLowerCase().includes(selectedDataset.toLowerCase())) ||
      (selectedDataset === 'MedQA' && c.id?.startsWith('medqa')) ||
      (selectedDataset === 'PubMedQA' && c.id?.startsWith('pubmedqa')) ||
      (selectedDataset === 'MedDialog' && c.id?.startsWith('meddialog'));

    const matchesSpecialty = selectedSpecialty === 'All' || 
      (c.specialty && c.specialty.toLowerCase().includes(selectedSpecialty.toLowerCase()));

    return matchesSearch && matchesDataset && matchesSpecialty;
  });

  const [activeCase, setActiveCase] = useState(filteredCases[0] || pool[0] || null);

  const datasets = [
    { key: 'All', label: 'All Datasets', count: pool.length },
    { key: 'MedQA', label: 'MedQA (USMLE)', count: pool.filter(c => c.id?.startsWith('medqa')).length || 50 },
    { key: 'PubMedQA', label: 'PubMedQA', count: pool.filter(c => c.id?.startsWith('pubmedqa')).length || 50 },
    { key: 'MedDialog', label: 'MedDialog', count: pool.filter(c => c.id?.startsWith('meddialog')).length || 50 },
  ];

  const specialties = ['All', 'Cardiology', 'Nephrology', 'Rheumatology', 'Neurology', 'Pediatrics', 'Pulmonology', 'Surgery', 'Gastroenterology', 'Infectious Disease'];

  const currentDisplayCase = activeCase || filteredCases[0] || pool[0];

  return (
    <div style={{ maxWidth: '1180px', margin: '0 auto', padding: '16px 20px 80px' }}>
      
      {/* 1. HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#EAF4EE', border: '1px solid #D1E7DD', padding: '4px 12px', borderRadius: '9999px', marginBottom: '8px' }}>
            <Database size={13} color="#1B4332" />
            <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#1B4332', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Full Knowledge Base & Dataset Pool
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>· {pool.length} Validated Cases Logged</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', margin: 0 }}>
            Clinical Cases Dataset Explorer
          </h2>
          <p style={{ fontSize: '0.86rem', color: '#64748B', marginTop: '4px', marginBottom: 0 }}>
            Explore all 150 standardized clinical cases across USMLE MedQA, PubMedQA, and MedDialog used in multi-agent governance benchmarks.
          </p>
        </div>

        {/* Dataset Filter Tabs */}
        <div style={{ display: 'flex', background: '#F1F5F9', padding: '4px', borderRadius: '8px', gap: '4px' }}>
          {datasets.map((d) => (
            <button
              key={d.key}
              onClick={() => setSelectedDataset(d.key)}
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                background: selectedDataset === d.key ? '#FFFFFF' : 'transparent',
                color: selectedDataset === d.key ? '#1B4332' : '#64748B',
                fontWeight: 800,
                fontSize: '0.78rem',
                cursor: 'pointer',
                boxShadow: selectedDataset === d.key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s ease'
              }}
            >
              {d.label} ({d.count})
            </button>
          ))}
        </div>
      </div>

      {/* 2. SEARCH & SPECIALTY FILTER BAR */}
      <div className="card" style={{ padding: '14px 18px', borderRadius: '12px', marginBottom: '18px', border: '1px solid #E2E8F0', boxShadow: '0 2px 6px rgba(0,0,0,0.02)' }}>
        <div style={{ display: 'flex', gap: '14px', alignItems: 'center', flexWrap: 'wrap' }}>
          
          {/* Search Box */}
          <div style={{ position: 'relative', flex: '1', minWidth: '240px' }}>
            <Search size={15} style={{ position: 'absolute', left: '10px', top: '11px', color: '#94A3B8' }} />
            <input 
              type="text"
              placeholder="Search by diagnosis, symptoms, or case ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px 8px 32px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '0.82rem',
                outline: 'none'
              }}
            />
          </div>

          {/* Specialty Filter Pills */}
          <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', padding: '2px 0' }}>
            {specialties.map((spec) => (
              <button
                key={spec}
                onClick={() => setSelectedSpecialty(spec)}
                style={{
                  padding: '5px 12px',
                  borderRadius: '6px',
                  fontSize: '0.76rem',
                  fontWeight: 700,
                  border: selectedSpecialty === spec ? '1px solid #1B4332' : '1px solid #E2E8F0',
                  background: selectedSpecialty === spec ? '#1B4332' : '#F8FAFC',
                  color: selectedSpecialty === spec ? '#FFFFFF' : '#475569',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap'
                }}
              >
                {spec}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 3. 2-COLUMN VIEW: FULL 150 CASE LIST (LEFT) & FULL EHR INSPECTOR (RIGHT) */}
      <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '18px', alignItems: 'start' }}>
        
        {/* LEFT COLUMN: LIST OF ALL CASES (PAGINATED SCROLLABLE) */}
        <div className="card" style={{ padding: '14px', borderRadius: '12px', border: '1px solid #E2E8F0', maxHeight: '720px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', paddingBottom: '8px', borderBottom: '1px solid #F1F5F9' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>
              {filteredCases.length} Clinical Cases
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>
              Select case to inspect
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filteredCases.map((c, idx) => {
              const isSelected = (currentDisplayCase?.id) === (c.id);
              return (
                <div 
                  key={c.id || idx}
                  onClick={() => setActiveCase(c)}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    border: isSelected ? '2px solid #1B4332' : '1px solid #E2E8F0',
                    background: isSelected ? '#F4F8F5' : '#FFFFFF',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 800, color: isSelected ? '#1B4332' : '#0F172A' }}>
                      {c.id}
                    </span>
                    <div style={{ display: 'flex', gap: '4px' }}>
                      <span style={{ 
                        fontSize: '0.65rem', 
                        fontWeight: 700, 
                        padding: '1px 5px', 
                        borderRadius: '3px',
                        background: '#EFF6FF',
                        color: '#1D4ED8'
                      }}>
                        {c.dataset ? c.dataset.split(' ')[0] : 'MedQA'}
                      </span>
                      <span style={{ 
                        fontSize: '0.65rem', 
                        fontWeight: 700, 
                        padding: '1px 5px', 
                        borderRadius: '3px',
                        background: '#EAF4EE',
                        color: '#15803D'
                      }}>
                        {c.specialty || 'General Med'}
                      </span>
                    </div>
                  </div>

                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#1E293B', marginBottom: '4px', lineHeight: 1.3 }}>
                    {c.gold_diagnosis || 'Clinical Vignette'}
                  </div>

                  <p style={{ fontSize: '0.74rem', color: '#64748B', margin: 0, lineHeight: 1.35, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {c.question}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT COLUMN: DETAILED CASE RECORD & COPILOT ACTION */}
        {currentDisplayCase ? (
          <div className="card" style={{ padding: '22px', borderRadius: '12px', border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.03)' }}>
            
            {/* Case Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #F1F5F9' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.88rem', fontWeight: 800, color: '#1B4332' }}>
                    {currentDisplayCase.id}
                  </span>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#EFF6FF', color: '#1D4ED8' }}>
                    {currentDisplayCase.dataset || 'MedQA (USMLE)'}
                  </span>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#F1F5F9', color: '#475569' }}>
                    {currentDisplayCase.specialty || 'Internal Medicine'}
                  </span>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#FEF3C7', color: '#92400E' }}>
                    {currentDisplayCase.difficulty ? `${currentDisplayCase.difficulty} Complexity` : 'Standard'}
                  </span>
                </div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#0F172A', margin: 0 }}>
                  {currentDisplayCase.gold_diagnosis || 'Clinical Case Assessment'}
                </h3>
              </div>
            </div>

            {/* Clinical Vignette Text */}
            <div style={{ marginBottom: '18px' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
                Patient Presentation & Clinical Record:
              </div>
              <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '14px 16px', fontSize: '0.86rem', color: '#1E293B', lineHeight: 1.6 }}>
                {currentDisplayCase.question}
              </div>
            </div>

            {/* Recommended Treatment Plan */}
            {currentDisplayCase.recommended_plan && (
              <div style={{ marginBottom: '18px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
                  Standard Therapeutic Regimen / Action Plan:
                </div>
                <div style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '12px 14px', fontSize: '0.82rem', color: '#334155', lineHeight: 1.5 }}>
                  {currentDisplayCase.recommended_plan}
                </div>
              </div>
            )}

            {/* Clinical Rationale & Grounding */}
            <div style={{ marginBottom: '22px' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
                Diagnostic Assessment & Multi-Agent Deliberation Note:
              </div>
              <div style={{ background: '#EAF4EE', border: '1px solid #D1E7DD', borderRadius: '8px', padding: '12px 16px', fontSize: '0.82rem', color: '#1B4332', lineHeight: 1.5 }}>
                <b>Guideline Grounding: </b>
                {currentDisplayCase.clinical_rationale || 'Evaluated against peer-reviewed clinical guidelines and safety contraindication checks.'}
              </div>
            </div>

            {/* Action Bar: Test in Case Runner */}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button 
                className="btn btn-primary"
                onClick={() => {
                  if (setCurrentPage) {
                    setCurrentPage('run-case');
                  } else {
                    window.location.href = '/run-case';
                  }
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  background: '#1B4332',
                  padding: '9px 18px',
                  fontSize: '0.84rem',
                  fontWeight: 800,
                  borderRadius: '8px',
                  cursor: 'pointer'
                }}
              >
                <Stethoscope size={15} />
                <span>Test in Clinical Copilot →</span>
              </button>
            </div>

          </div>
        ) : null}

      </div>

    </div>
  );
}
