import React, { useState } from 'react';
import { 
  GitFork, 
  ShieldAlert, 
  ShieldCheck, 
  UserCheck, 
  BookOpen, 
  Stethoscope, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  ArrowRight, 
  Sparkles,
  Layers,
  FileText,
  AlertTriangle,
  ChevronRight
} from 'lucide-react';

export default function AgentPipeline() {
  const [activeTab, setActiveTab] = useState('topology'); // 'topology' | 'governance'
  const [selectedAgent, setSelectedAgent] = useState('safety');

  const agents = [
    {
      id: 'case',
      role: 'EHR Ingestion Node',
      title: 'Patient Clinical Vignette',
      tag: 'Input Source',
      tagColor: '#64748B',
      icon: <FileText size={18} color="#64748B" />,
      desc: 'Ingests clinical narrative, vitals, lab values, and past medical history from USMLE / EHR records.',
      promptSummary: 'Extracts demographics, chief complaint, pertinent positives/negatives, and baseline organ function (e.g. eGFR, LFTs).',
      latency: 'Instant',
      compute: '0 tokens'
    },
    {
      id: 'specialist',
      role: 'Diagnostic Reasoner',
      title: 'Lead Specialist Agent',
      tag: 'Diagnostics',
      tagColor: '#2563EB',
      icon: <Stethoscope size={18} color="#2563EB" />,
      desc: 'Formulates initial differential diagnoses ranked by Bayesian likelihood and proposes candidate pharmacotherapy.',
      promptSummary: 'Performs clinical reasoning step-by-step: Key clues ➔ Hypotheses ➔ Contradiction elimination ➔ Ranked differential.',
      latency: '0.82 s',
      compute: '1,867 tokens'
    },
    {
      id: 'researcher',
      role: 'Evidence Grounder',
      title: 'Literature Researcher',
      tag: 'Fact-Check',
      tagColor: '#D97706',
      icon: <BookOpen size={18} color="#D97706" />,
      desc: 'Grounds candidate diagnostic claims against PubMed literature, ACR, AHA, and KDIGO practice guidelines.',
      promptSummary: 'Queries medical knowledge base for Level A randomized controlled trials and peer-reviewed consensus recommendations.',
      latency: '0.45 s',
      compute: '1,240 tokens'
    },
    {
      id: 'safety',
      role: 'Deterministic Guardrail',
      title: 'Safety Validator Agent',
      tag: 'Hazard Interceptor',
      tagColor: '#DC2626',
      icon: <ShieldAlert size={18} color="#DC2626" />,
      desc: 'Scans proposed prescriptions against organ dysfunction rules (e.g. CKD 3b, hepatic failure, coagulopathy).',
      promptSummary: 'Deterministic rule engine: If eGFR < 60 mL/min & drug == NSAID ➔ TRIGGER HAZARD: Block prescription & substitute steroid.',
      latency: '0.12 s',
      compute: '620 tokens'
    },
    {
      id: 'hitl',
      role: 'Physician Gate',
      title: 'Attending HITL Gate',
      tag: 'Clinical Signoff',
      tagColor: '#16A34A',
      icon: <UserCheck size={18} color="#16A34A" />,
      desc: 'Enforces attending physician verification on high-risk treatments and complex multi-morbid cases.',
      promptSummary: 'Attending reviews differential justification, safety audit trace, and signs off on final EHR prescription note.',
      latency: 'Gated',
      compute: '710 tokens'
    }
  ];

  const levels = [
    {
      id: 'G0',
      title: 'Baseline (Ungoverned)',
      subtitle: 'Raw LLM Direct Inference',
      desc: 'Single specialist prompt without verification or safety checks. Replicates standard unmonitored LLM medical advice.',
      badgeColor: '#64748B',
      accuracy: '73.4%',
      safetyCaught: '0.00 / case',
      latency: '38.5 s',
      tokens: '3,106',
      cost: '$0.0004',
      features: [
        { label: 'Diagnostic Reasoning', active: true },
        { label: 'Literature Grounding', active: false },
        { label: 'Safety Interception Guardrails', active: false },
        { label: 'Attending Physician Signoff', active: false }
      ],
      hazardNotice: 'Allowed fatal drug contraindications through on 100% of benchmark test cases.'
    },
    {
      id: 'G1',
      title: 'Literature Verification',
      subtitle: 'PubMed & Guideline Grounding',
      desc: 'Adds neural fact-checking agent against peer-reviewed guidelines to eliminate hallucinations.',
      badgeColor: '#2563EB',
      accuracy: '74.0%',
      safetyCaught: '0.00 / case',
      latency: '59.6 s',
      tokens: '4,989',
      cost: '$0.0007',
      features: [
        { label: 'Diagnostic Reasoning', active: true },
        { label: 'Literature Grounding', active: true },
        { label: 'Safety Interception Guardrails', active: false },
        { label: 'Attending Physician Signoff', active: false }
      ],
      hazardNotice: 'Eliminates fabricated citations but remains blind to physiological organ contraindications.'
    },
    {
      id: 'G2',
      title: 'Attending HITL Gate',
      subtitle: 'Human-in-the-Loop Oversight',
      desc: 'Requires formal simulated or live attending physician review and approval on treatment plans.',
      badgeColor: '#D97706',
      accuracy: '74.0%',
      safetyCaught: '0.00 / case',
      latency: '39.1 s',
      tokens: '4,687',
      cost: '$0.0006',
      features: [
        { label: 'Diagnostic Reasoning', active: true },
        { label: 'Literature Grounding', active: false },
        { label: 'Safety Interception Guardrails', active: false },
        { label: 'Attending Physician Signoff', active: true }
      ],
      hazardNotice: 'High clinical oversight but manual review increases physician cognitive burden.'
    },
    {
      id: 'G3',
      title: 'Safety Guardrails',
      subtitle: 'Deterministic Rule Engine',
      desc: 'Automated organ contraindication interceptor. Pareto optimal for acute clinical safety.',
      badgeColor: '#16A34A',
      accuracy: '74.1%',
      safetyCaught: '1.89 / case',
      latency: '45.4 s',
      tokens: '4,848',
      cost: '$0.0006',
      features: [
        { label: 'Diagnostic Reasoning', active: true },
        { label: 'Literature Grounding', active: false },
        { label: 'Safety Interception Guardrails', active: true },
        { label: 'Attending Physician Signoff', active: false }
      ],
      hazardNotice: 'Neutralized 284 out of 285 fatal contraindications before reaching prescription output.'
    },
    {
      id: 'G4',
      title: 'Defense-in-Depth',
      subtitle: 'Full Multi-Agent Consensus',
      desc: 'Simultaneous deployment of Literature Verification, Deterministic Safety Guardrails, and Attending Signoff.',
      badgeColor: '#7C3AED',
      accuracy: '74.1%',
      safetyCaught: '1.90 / case (285 total)',
      latency: '95.5 s',
      tokens: '8,411',
      cost: '$0.0011',
      features: [
        { label: 'Diagnostic Reasoning', active: true },
        { label: 'Literature Grounding', active: true },
        { label: 'Safety Interception Guardrails', active: true },
        { label: 'Attending Physician Signoff', active: true }
      ],
      hazardNotice: 'Recommended enterprise protocol for Intensive Care and High-Acuity Emergency Medicine.'
    }
  ];

  const currentAgent = agents.find((a) => a.id === selectedAgent) || agents[3];

  return (
    <div style={{ maxWidth: '1180px', margin: '0 auto', padding: '16px 20px 80px' }}>
      
      {/* 1. HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '22px' }}>
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#EAF4EE', border: '1px solid #D1E7DD', padding: '4px 12px', borderRadius: '9999px', marginBottom: '8px' }}>
            <GitFork size={13} color="#1B4332" />
            <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#1B4332', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Multi-Agent Architecture
            </span>
            <span style={{ fontSize: '0.72rem', color: '#64748B' }}>· Consensus Deliberation Topology</span>
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', margin: 0 }}>
            Agent Pipeline & Governance Architecture
          </h2>
          <p style={{ fontSize: '0.86rem', color: '#64748B', marginTop: '4px', marginBottom: 0 }}>
            Explore the 5-node clinical deliberation consensus flow and formal G0–G4 governance safety tiers.
          </p>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', background: '#F1F5F9', padding: '4px', borderRadius: '8px', gap: '4px' }}>
          <button
            onClick={() => setActiveTab('topology')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'topology' ? '#FFFFFF' : 'transparent',
              color: activeTab === 'topology' ? '#1B4332' : '#64748B',
              fontWeight: 800,
              fontSize: '0.8rem',
              cursor: 'pointer',
              boxShadow: activeTab === 'topology' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
              transition: 'all 0.15s ease'
            }}
          >
            Deliberation Flow
          </button>
          <button
            onClick={() => setActiveTab('governance')}
            style={{
              padding: '6px 16px',
              borderRadius: '6px',
              border: 'none',
              background: activeTab === 'governance' ? '#FFFFFF' : 'transparent',
              color: activeTab === 'governance' ? '#1B4332' : '#64748B',
              fontWeight: 800,
              fontSize: '0.8rem',
              cursor: 'pointer',
              boxShadow: activeTab === 'governance' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
              transition: 'all 0.15s ease'
            }}
          >
            Governance Tiers (G0–G4)
          </button>
        </div>
      </div>

      {activeTab === 'topology' ? (
        <>
          {/* 2. TOPOLOGY STEPPING PIPELINE */}
          <div className="card" style={{ padding: '22px', borderRadius: '14px', marginBottom: '22px', border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <span style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0F172A' }}>Sequential Multi-Agent Deliberation Flow</span>
                <span style={{ fontSize: '0.74rem', color: '#64748B', display: 'block' }}>Click any agent node below to inspect prompt instructions and execution roles</span>
              </div>
              <span style={{ fontSize: '0.72rem', fontWeight: 800, padding: '3px 10px', borderRadius: '9999px', background: '#DCFCE7', color: '#15803D' }}>
                🟢 Status: Active (G4 Mode)
              </span>
            </div>

            {/* Visual Connected Nodes */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', alignItems: 'center' }}>
              {agents.map((ag, idx) => {
                const isSelected = selectedAgent === ag.id;
                return (
                  <div
                    key={ag.id}
                    onClick={() => setSelectedAgent(ag.id)}
                    style={{
                      background: isSelected ? '#FFFFFF' : '#F8FAFC',
                      border: isSelected ? `2px solid ${ag.tagColor}` : '1px solid #E2E8F0',
                      borderRadius: '10px',
                      padding: '12px 10px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? `0 4px 14px ${ag.tagColor}22` : 'none',
                      textAlign: 'center',
                      position: 'relative'
                    }}
                  >
                    <div style={{ 
                      width: '36px', 
                      height: '36px', 
                      borderRadius: '50%', 
                      background: `${ag.tagColor}15`, 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      margin: '0 auto 8px' 
                    }}>
                      {ag.icon}
                    </div>

                    <div style={{ fontSize: '0.68rem', fontWeight: 800, color: ag.tagColor, textTransform: 'uppercase' }}>
                      Step 0{idx + 1}
                    </div>

                    <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A', marginTop: '2px', lineHeight: 1.2 }}>
                      {ag.title}
                    </div>

                    <div style={{ fontSize: '0.7rem', color: '#64748B', marginTop: '3px' }}>
                      {ag.role}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3. SELECTED AGENT DEEP-DIVE INSPECTOR */}
          <div className="card" style={{ padding: '22px', borderRadius: '14px', border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.02)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', paddingBottom: '12px', borderBottom: '1px solid #F1F5F9' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: `${currentAgent.tagColor}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {currentAgent.icon}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>{currentAgent.title}</span>
                    <span style={{ fontSize: '0.68rem', fontWeight: 800, padding: '2px 8px', borderRadius: '4px', background: `${currentAgent.tagColor}15`, color: currentAgent.tagColor }}>
                      {currentAgent.tag}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#64748B' }}>Architectural Specification & Responsibility</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '14px' }}>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.68rem', color: '#64748B', display: 'block' }}>Typical Latency</span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>{currentAgent.latency}</span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: '0.68rem', color: '#64748B', display: 'block' }}>Compute Tokens</span>
                  <span style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>{currentAgent.compute}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '18px' }}>
              <div>
                <div style={{ fontSize: '0.74rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Agent Responsibility:
                </div>
                <p style={{ fontSize: '0.84rem', color: '#334155', lineHeight: 1.5, marginBottom: '14px' }}>
                  {currentAgent.desc}
                </p>

                <div style={{ fontSize: '0.74rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Execution Protocol & Prompt Logic:
                </div>
                <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '12px 14px', fontSize: '0.8rem', color: '#1E293B', fontFamily: 'monospace', lineHeight: 1.45 }}>
                  {currentAgent.promptSummary}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '0.74rem', fontWeight: 800, color: '#64748B', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Verified Clinical Safeguards:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ background: '#F0FDF4', border: '1px solid #DCFCE7', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem', color: '#15803D' }}>
                    <b>✓ Consensus Check:</b> Output must adhere to Level A practice guidelines before proceeding to downstream agents.
                  </div>
                  <div style={{ background: '#FEF2F2', border: '1px solid #FEE2E2', borderRadius: '8px', padding: '10px 12px', fontSize: '0.78rem', color: '#DC2626' }}>
                    <b>🚨 Fatal Error Veto:</b> Immediate override authority if drug contraindications or organ toxicity risks are identified.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : (
        /* 4. GOVERNANCE TIERS G0–G4 CARDS */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {levels.map((lvl) => (
            <div
              key={lvl.id}
              className="card"
              style={{
                padding: '18px 22px',
                borderRadius: '12px',
                border: lvl.id === 'G4' ? '2px solid #7C3AED' : '1px solid #E2E8F0',
                boxShadow: '0 2px 8px rgba(0,0,0,0.02)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                    <span style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>
                      {lvl.id}: {lvl.title}
                    </span>
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: `${lvl.badgeColor}15`, color: lvl.badgeColor }}>
                      {lvl.subtitle}
                    </span>
                    {lvl.id === 'G4' && (
                      <span style={{ fontSize: '0.68rem', fontWeight: 800, padding: '2px 8px', borderRadius: '9999px', background: '#7C3AED', color: '#FFFFFF' }}>
                        Enterprise Recommended
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.8rem', color: '#475569', margin: 0 }}>
                    {lvl.desc}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '16px', textAlign: 'right' }}>
                  <div>
                    <span style={{ fontSize: '0.68rem', color: '#64748B', display: 'block' }}>Accuracy</span>
                    <span style={{ fontSize: '0.92rem', fontWeight: 800, color: '#0F172A' }}>{lvl.accuracy}</span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.68rem', color: '#64748B', display: 'block' }}>Contraindications</span>
                    <span style={{ fontSize: '0.92rem', fontWeight: 800, color: lvl.safetyCaught.includes('0.00') ? '#DC2626' : '#15803D' }}>
                      {lvl.safetyCaught}
                    </span>
                  </div>
                  <div>
                    <span style={{ fontSize: '0.68rem', color: '#64748B', display: 'block' }}>Cost / Case</span>
                    <span style={{ fontSize: '0.92rem', fontWeight: 800, color: '#2563EB' }}>{lvl.cost}</span>
                  </div>
                </div>
              </div>

              {/* Feature Checklist */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', paddingTop: '10px', borderTop: '1px solid #F1F5F9' }}>
                {lvl.features.map((feat, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.76rem' }}>
                    <span style={{ color: feat.active ? '#15803D' : '#94A3B8' }}>
                      {feat.active ? <CheckCircle2 size={14} /> : '○'}
                    </span>
                    <span style={{ color: feat.active ? '#0F172A' : '#94A3B8', fontWeight: feat.active ? 600 : 400 }}>
                      {feat.label}
                    </span>
                  </div>
                ))}
              </div>

              {/* Safety notice */}
              <div style={{ marginTop: '10px', fontSize: '0.74rem', color: lvl.id === 'G0' ? '#DC2626' : '#64748B', fontStyle: 'italic' }}>
                Clinical Note: {lvl.hazardNotice}
              </div>
            </div>
          ))}
        </div>
      )}

    </div>
  );
}
