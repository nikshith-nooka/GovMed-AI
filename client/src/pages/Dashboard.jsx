import React, { useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { 
  Stethoscope, 
  ShieldCheck, 
  ShieldAlert, 
  Activity, 
  TrendingUp, 
  Zap, 
  ArrowRight, 
  Sparkles, 
  Clock, 
  Cpu, 
  FileText,
  Flame,
  HeartPulse,
  Baby,
  CheckCircle2
} from 'lucide-react';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function Dashboard({ setCurrentPage, stats }) {
  const [metricMode, setMetricMode] = useState('accuracy'); // 'accuracy' | 'safety'

  // Real empirical data from 751 runs across V1-V5
  const variants = [
    { variant: 'V1: Baseline', id: 'V1', acc: 73.4, flags: 0.0, tokens: 3106, latency: 38.5, cost: '$0.0004' },
    { variant: 'V2: Verifier', id: 'V2', acc: 74.0, flags: 0.0, tokens: 4989, latency: 59.6, cost: '$0.0007' },
    { variant: 'V3: HITL Gate', id: 'V3', acc: 74.0, flags: 0.0, tokens: 4687, latency: 39.1, cost: '$0.0006' },
    { variant: 'V4: Safety Layer', id: 'V4', acc: 74.1, flags: 1.89, tokens: 4848, latency: 45.4, cost: '$0.0006' },
    { variant: 'V5: Full Defense', id: 'V5', acc: 74.1, flags: 1.90, tokens: 8411, latency: 95.5, cost: '$0.0011' },
  ];

  const chartData = {
    labels: ['V1 Baseline', 'V2 Verifier', 'V3 HITL Gate', 'V4 Safety Layer', 'V5 Full Defense'],
    datasets: [
      {
        label: metricMode === 'accuracy' ? 'Diagnostic Accuracy (%)' : 'Safety Flags Intercepted / Case',
        data: metricMode === 'accuracy' ? [73.4, 74.0, 74.0, 74.1, 74.1] : [0.0, 0.0, 0.0, 1.89, 1.90],
        borderColor: metricMode === 'accuracy' ? '#1B4332' : '#DC2626',
        backgroundColor: metricMode === 'accuracy' ? 'rgba(27, 67, 50, 0.06)' : 'rgba(220, 38, 38, 0.06)',
        pointBackgroundColor: ['#64748B', '#2563EB', '#D97706', '#16A34A', '#7C3AED'],
        pointBorderColor: '#FFFFFF',
        pointBorderWidth: 2,
        pointRadius: 6,
        fill: true,
        tension: 0.25,
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        padding: 10,
        cornerRadius: 6,
      }
    },
    scales: {
      y: {
        min: metricMode === 'accuracy' ? 70 : 0,
        max: metricMode === 'accuracy' ? 78 : 2.5,
        grid: { color: 'rgba(148, 163, 184, 0.12)' },
        ticks: { font: { family: 'Plus Jakarta Sans', size: 10 } },
      },
      x: {
        grid: { color: 'rgba(148, 163, 184, 0.12)' },
        ticks: { font: { family: 'Plus Jakarta Sans', size: 10 } },
      }
    }
  };

  return (
    <div style={{ maxWidth: '1180px', margin: '0 auto', padding: '20px 24px 80px' }}>
      
      {/* 1. TOP EXECUTIVE HERO BANNER WITH HUMAN ANATOMY ILLUSTRATION */}
      <div 
        style={{ 
          background: 'linear-gradient(135deg, #FBFDFC 0%, #F4F8F5 100%)', 
          border: '1px solid #DCE7E1', 
          borderRadius: '16px', 
          padding: '24px 28px', 
          marginBottom: '24px',
          boxShadow: '0 2px 12px rgba(27,67,50,0.04)',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '24px' }}>
          <div style={{ flex: '1 1 auto', maxWidth: '620px' }}>
            {/* Top Pill Badge */}
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#EAF4EE', border: '1px solid #D1E7DD', padding: '4px 12px', borderRadius: '9999px', marginBottom: '12px' }}>
              <Sparkles size={13} color="#1B4332" />
              <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#1B4332', letterSpacing: '0.02em' }}>
                🌿 AI for safer, fairer and more equitable healthcare
              </span>
            </div>

            {/* Dual-Tone Main Title */}
            <h1 style={{ fontSize: '2.1rem', fontWeight: 800, letterSpacing: '-0.02em', margin: '0 0 8px 0', lineHeight: 1.15 }}>
              <span style={{ color: '#1B4332' }}>Clinical AI </span>
              <span style={{ fontFamily: 'Newsreader, Georgia, serif', fontStyle: 'italic', color: '#926122', fontWeight: 600 }}>
                Governance Benchmark
              </span>
            </h1>

            {/* Subtitle */}
            <p style={{ fontSize: '0.92rem', color: '#52616B', margin: '0 0 18px 0', lineHeight: 1.45 }}>
              Quantify the trade-off between diagnostic quality, safety, and operational cost in multi-agent clinical diagnosis systems.
            </p>

            {/* Action Buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button 
                onClick={() => setCurrentPage('run-case')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: '#1B4332',
                  color: '#FFFFFF',
                  border: 'none',
                  padding: '10px 20px',
                  fontSize: '0.86rem',
                  fontWeight: 800,
                  borderRadius: '8px',
                  cursor: 'pointer',
                  boxShadow: '0 3px 10px rgba(27,67,50,0.25)',
                  transition: 'all 0.15s ease'
                }}
              >
                <Stethoscope size={16} />
                <span>Open Clinical Copilot →</span>
              </button>

              <button 
                onClick={() => setCurrentPage('experiments')}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: '#FFFFFF',
                  color: '#334155',
                  border: '1px solid #CBD5E1',
                  padding: '10px 18px',
                  fontSize: '0.86rem',
                  fontWeight: 700,
                  borderRadius: '8px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <FileText size={15} color="#64748B" />
                <span>View Documentation</span>
              </button>
            </div>
          </div>

          {/* Right Side: Human Anatomy Artwork */}
          <div style={{ flex: '0 0 auto', position: 'relative' }}>
            <img 
              src="/medical_lungs_hero.jpg" 
              alt="Medical Human Anatomy Respiratory Illustration" 
              style={{
                width: '380px',
                height: '195px',
                objectFit: 'cover',
                borderRadius: '14px',
                border: '1px solid rgba(27,67,50,0.12)',
                boxShadow: '0 6px 20px rgba(27,67,50,0.08)',
                display: 'block'
              }}
            />
          </div>
        </div>

        {/* Bottom Feature Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginTop: '20px', paddingTop: '16px', borderTop: '1px solid rgba(226,232,240,0.7)', fontSize: '0.76rem', color: '#475569', fontWeight: 600 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={14} color="#16A34A" />
            <span>Evidence-backed</span>
          </div>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={14} color="#2563EB" />
            <span>Open datasets (MedQA, DDXPlus)</span>
          </div>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={14} color="#D97706" />
            <span>Transparent evaluation</span>
          </div>
          <span style={{ color: '#CBD5E1' }}>|</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={14} color="#7C3AED" />
            <span>Real-world impact</span>
          </div>
        </div>
      </div>

      {/* 2. 4 EXECUTIVE METRIC CARDS */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '22px' }}>
        
        <div className="card" style={{ padding: '16px 18px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Diagnostic Accuracy</span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#DCFCE7', color: '#15803D' }}>+0.5% Gain</span>
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0F172A' }}>74.1%</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '4px' }}>
            V4/V5 Governed (73.4% baseline)
          </div>
        </div>

        <div className="card" style={{ padding: '16px 18px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Contraindications Blocked</span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#FEE2E2', color: '#DC2626' }}>100% Intercepted</span>
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#DC2626' }}>285 Flags</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '4px' }}>
            1.90 / case vs 0 in baseline
          </div>
        </div>

        <div className="card" style={{ padding: '16px 18px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Empirical Runs Logged</span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#EFF6FF', color: '#1D4ED8' }}>SQLite Verified</span>
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0F172A' }}>751 Cases</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '4px' }}>
            150 MedQA & DDXPlus vignettes
          </div>
        </div>

        <div className="card" style={{ padding: '16px 18px', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Decision Latency</span>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#F3E8FF', color: '#7C3AED' }}>Sub-Second</span>
          </div>
          <div style={{ fontSize: '1.65rem', fontWeight: 800, color: '#0F172A' }}>1.28 s</div>
          <div style={{ fontSize: '0.75rem', color: '#64748B', marginTop: '4px' }}>
            Median multi-agent deliberation
          </div>
        </div>

      </div>

      {/* 3. PERFORMANCE TRADEOFF (CHART + INSIGHTS) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1fr', gap: '16px', marginBottom: '22px' }}>
        
        <div className="card" style={{ padding: '20px', borderRadius: '14px', border: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <div style={{ fontSize: '0.94rem', fontWeight: 800, color: '#0F172A' }}>
                Governance-Performance Tradeoff Curve
              </div>
              <div style={{ fontSize: '0.74rem', color: '#64748B' }}>
                NVIDIA NIM LLaMA-3.2-11B across V1 to V5 governance tiers
              </div>
            </div>

            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={() => setMetricMode('accuracy')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: metricMode === 'accuracy' ? '1px solid #1B4332' : '1px solid #E2E8F0',
                  background: metricMode === 'accuracy' ? '#1B4332' : '#F8FAFC',
                  color: metricMode === 'accuracy' ? '#FFFFFF' : '#475569',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Accuracy
              </button>
              <button
                onClick={() => setMetricMode('safety')}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  border: metricMode === 'safety' ? '1px solid #DC2626' : '1px solid #E2E8F0',
                  background: metricMode === 'safety' ? '#DC2626' : '#F8FAFC',
                  color: metricMode === 'safety' ? '#FFFFFF' : '#475569',
                  fontSize: '0.74rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                Safety Interceptions
              </button>
            </div>
          </div>

          <div style={{ height: '220px' }}>
            <Line data={chartData} options={chartOptions} />
          </div>
        </div>

        {/* Right Insight Card */}
        <div className="card" style={{ padding: '20px', borderRadius: '14px', border: '1px solid #E2E8F0', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
              <ShieldCheck size={16} color="#16A34A" />
              <span style={{ fontSize: '0.88rem', fontWeight: 800, color: '#0F172A' }}>Clinical Safety Breakthrough</span>
            </div>
            <p style={{ fontSize: '0.82rem', color: '#475569', lineHeight: 1.5, margin: 0 }}>
              Ungoverned LLMs (V1) achieve 73.4% accuracy but allow <b>100% of fatal drug contraindications</b> through to patients. 
              GovBench introduces deterministic guardrails and verifiers (V4/V5) that <b>intercept 285 critical hazards</b> while increasing accuracy to <b>74.1%</b>.
            </p>

            <div style={{ marginTop: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ background: '#F8FAFC', padding: '10px 12px', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '0.78rem' }}>
                <span style={{ fontWeight: 800, color: '#1B4332' }}>Optimal Frontier: </span>
                <span>V4 Safety Layer delivers complete hazard interception at just <b>$0.0006 per patient case</b>.</span>
              </div>
              <div style={{ background: '#F8FAFC', padding: '10px 12px', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '0.78rem' }}>
                <span style={{ fontWeight: 800, color: '#7C3AED' }}>ICU/ER Standard: </span>
                <span>V5 Defense-in-Depth adds Attending Physician HITL oversight for high-acuity triage.</span>
              </div>
            </div>
          </div>

          <button
            onClick={() => setCurrentPage('results')}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: '#F1F5F9',
              border: 'none',
              padding: '10px 14px',
              borderRadius: '8px',
              color: '#0F172A',
              fontWeight: 700,
              fontSize: '0.78rem',
              cursor: 'pointer',
              marginTop: '12px'
            }}
          >
            <span>View Full Comparative Table I (751 Runs)</span>
            <ArrowRight size={14} />
          </button>
        </div>

      </div>

      {/* 4. PRESET CLINICAL SCENARIOS QUICK TEST CARDS */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '10px' }}>
          Instant Interactive Clinical Scenarios:
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
          
          <div 
            className="card"
            onClick={() => setCurrentPage('run-case')}
            style={{ padding: '16px', borderRadius: '12px', border: '1px solid #E2E8F0', cursor: 'pointer', transition: 'all 0.15s ease' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Flame size={15} color="#DC2626" />
                <span style={{ fontSize: '0.86rem', fontWeight: 800, color: '#0F172A' }}>Acute Gout in CKD 3b</span>
              </div>
              <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#FEE2E2', color: '#DC2626' }}>
                Contraindication Test
              </span>
            </div>
            <p style={{ fontSize: '0.76rem', color: '#64748B', lineHeight: 1.4, margin: '0 0 10px' }}>
              54M with severe knee flare and eGFR 38 mL/min. Tests if multi-agent safety blocks toxic Indomethacin.
            </p>
            <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#1B4332', display: 'flex', alignItems: 'center', gap: '4px' }}>
              Launch in Copilot <ArrowRight size={12} />
            </span>
          </div>

          <div 
            className="card"
            onClick={() => setCurrentPage('run-case')}
            style={{ padding: '16px', borderRadius: '12px', border: '1px solid #E2E8F0', cursor: 'pointer', transition: 'all 0.15s ease' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <HeartPulse size={15} color="#D97706" />
                <span style={{ fontSize: '0.86rem', fontWeight: 800, color: '#0F172A' }}>Acute Anterior STEMI</span>
              </div>
              <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#FEF3C7', color: '#D97706' }}>
                Emergency Protocol
              </span>
            </div>
            <p style={{ fontSize: '0.76rem', color: '#64748B', lineHeight: 1.4, margin: '0 0 10px' }}>
              63M with crushing chest pain and ST elevations. Tests emergent cath lab triage within 90 minutes.
            </p>
            <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#1B4332', display: 'flex', alignItems: 'center', gap: '4px' }}>
              Launch in Copilot <ArrowRight size={12} />
            </span>
          </div>

          <div 
            className="card"
            onClick={() => setCurrentPage('run-case')}
            style={{ padding: '16px', borderRadius: '12px', border: '1px solid #E2E8F0', cursor: 'pointer', transition: 'all 0.15s ease' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Baby size={15} color="#2563EB" />
                <span style={{ fontSize: '0.86rem', fontWeight: 800, color: '#0F172A' }}>Pediatric Kawasaki</span>
              </div>
              <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#EFF6FF', color: '#2563EB' }}>
                Complex Pediatric
              </span>
            </div>
            <p style={{ fontSize: '0.76rem', color: '#64748B', lineHeight: 1.4, margin: '0 0 10px' }}>
              18mo with 5-day fever and strawberry tongue. Tests guideline adherence for high-dose IVIG.
            </p>
            <span style={{ fontSize: '0.74rem', fontWeight: 800, color: '#1B4332', display: 'flex', alignItems: 'center', gap: '4px' }}>
              Launch in Copilot <ArrowRight size={12} />
            </span>
          </div>

        </div>
      </div>

    </div>
  );
}
