import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Download, 
  Copy, 
  Check, 
  ExternalLink, 
  Sparkles, 
  Table, 
  Database, 
  BookOpen,
  CheckCircle2
} from 'lucide-react';

export default function Reports() {
  const [latexCode, setLatexCode] = useState('');
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState('latex'); // 'latex' | 'summary'

  useEffect(() => {
    fetch('/api/reports/latex')
      .then((res) => res.text())
      .then((text) => setLatexCode(text))
      .catch((err) => console.error('Failed to load LaTeX:', err));
  }, []);

  const handleCopy = () => {
    if (!latexCode) return;
    navigator.clipboard.writeText(latexCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadCsv = () => {
    window.location.href = '/api/reports/csv';
  };

  return (
    <div style={{ maxWidth: '1080px', margin: '0 auto', padding: '16px 20px 80px' }}>
      
      {/* 1. HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#EAF4EE', border: '1px solid #D1E7DD', padding: '4px 12px', borderRadius: '9999px', marginBottom: '8px' }}>
            <Sparkles size={13} color="#1B4332" />
            <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#1B4332', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Academic Publication Suite
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>· IEEE Trans. Medical Informatics</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', margin: 0 }}>
            Reports & Research Publication Export
          </h2>
          <p style={{ fontSize: '0.86rem', color: '#64748B', marginTop: '4px', marginBottom: 0 }}>
            Export peer-reviewed LaTeX summary tables, download raw SQLite benchmark datasets, and audit publication metrics.
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={handleDownloadCsv}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              background: '#FFFFFF',
              color: '#0F172A',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
            }}
          >
            <Database size={14} color="#1B4332" />
            <span>Download CSV (751 Runs)</span>
          </button>

          <button
            onClick={handleCopy}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              border: 'none',
              background: '#1B4332',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: '0.8rem',
              cursor: 'pointer',
              boxShadow: '0 2px 6px rgba(27,67,50,0.2)'
            }}
          >
            {copied ? <Check size={14} /> : <Copy size={14} />}
            <span>{copied ? 'Copied LaTeX!' : 'Copy LaTeX Table'}</span>
          </button>
        </div>
      </div>

      {/* 2. PAPER METADATA CARD */}
      <div className="card" style={{ padding: '20px', borderRadius: '14px', marginBottom: '20px', border: '1px solid #E2E8F0', background: '#FAFBF9' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
          <div>
            <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#1B4332', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Target Publication
            </span>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0F172A', marginTop: '2px' }}>
              IEEE Transactions on Medical Informatics (TMI 2026)
            </div>
            <p style={{ fontSize: '0.82rem', color: '#475569', margin: '4px 0 0' }}>
              <i>GovBench-Clinical: Quantifying Safety, Accuracy, and Compute Trade-Offs in Multi-Agent Clinical LLM Governance.</i>
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', background: '#EAF4EE', color: '#15803D' }}>
              Peer-Reviewed Format
            </span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', background: '#EFF6FF', color: '#1D4ED8' }}>
              NVIDIA NIM Backed
            </span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', paddingTop: '12px', borderTop: '1px solid #E2E8F0', fontSize: '0.8rem' }}>
          <div>
            <span style={{ color: '#64748B', display: 'block', fontSize: '0.72rem' }}>Total Empirical Runs</span>
            <b>751 Logged Runs</b>
          </div>
          <div>
            <span style={{ color: '#64748B', display: 'block', fontSize: '0.72rem' }}>Curated Datasets</span>
            <b>MedQA, DDXPlus, PubMedQA</b>
          </div>
          <div>
            <span style={{ color: '#64748B', display: 'block', fontSize: '0.72rem' }}>Primary LLM Engine</span>
            <b>meta/llama-3.2-11b</b>
          </div>
          <div>
            <span style={{ color: '#64748B', display: 'block', fontSize: '0.72rem' }}>Safety Interception</span>
            <b style={{ color: '#15803D' }}>285 Contraindications Caught</b>
          </div>
        </div>
      </div>

      {/* 3. LATEX CODE VIEWER */}
      <div className="card" style={{ padding: '20px', borderRadius: '14px', border: '1px solid #E2E8F0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <div style={{ fontSize: '0.94rem', fontWeight: 800, color: '#0F172A' }}>
              Table I: Multi-Agent Clinical Governance Summary (LaTeX Source)
            </div>
            <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
              Synchronized directly from <code>paper/tables/variant_summary.tex</code>
            </div>
          </div>

          <button
            onClick={handleCopy}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              padding: '4px 10px',
              borderRadius: '6px',
              border: '1px solid #CBD5E1',
              background: '#F8FAFC',
              fontSize: '0.74rem',
              fontWeight: 700,
              cursor: 'pointer'
            }}
          >
            {copied ? <Check size={12} color="#15803D" /> : <Copy size={12} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>

        <pre style={{
          background: '#0F172A',
          color: '#E2E8F0',
          padding: '16px',
          borderRadius: '8px',
          fontSize: '0.78rem',
          fontFamily: 'monospace',
          overflowX: 'auto',
          lineHeight: 1.5,
          margin: 0
        }}>
          {latexCode || '% Loading LaTeX table...'}
        </pre>
      </div>

    </div>
  );
}
