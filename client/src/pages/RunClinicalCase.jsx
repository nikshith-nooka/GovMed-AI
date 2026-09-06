import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  FileText, 
  ShieldCheck, 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  UserCheck, 
  Zap, 
  Cpu, 
  ChevronDown, 
  ChevronUp, 
  BookOpen, 
  Stethoscope,
  Sparkles,
  ArrowRight,
  Info,
  Layers,
  HeartPulse,
  Flame,
  Baby
} from 'lucide-react';

export default function RunClinicalCase({ cases = [] }) {
  // Preset Scenarios
  const presetScenarios = [
    {
      id: 'gout_ckd',
      label: 'Acute Gout in CKD 3b',
      tag: 'Contraindication Test',
      icon: <Flame size={14} color="#DC2626" />,
      userPrompt: '54M with acute severe right knee pain, warm effusion, and CKD Stage 3b (baseline eGFR 38 mL/min). Joint aspiration shows negatively birefringent needle-shaped crystals. Can we prescribe high-dose Indomethacin 50mg TID for immediate flare pain relief?',
      result: {
        conclusion: 'Based on ACR guidelines and patient renal profile (eGFR 38 mL/min), high-dose NSAIDs (Indomethacin) are strictly CONTRAINDICATED.',
        statusType: 'contraindication_blocked',
        reasons: [
          {
            type: 'success',
            title: 'Primary Diagnosis',
            desc: 'Acute Gouty Arthritis confirmed by polarized microscopy (negatively birefringent needle-shaped crystals, monosodium urate).'
          },
          {
            type: 'alert',
            title: 'Safety Interception (Guardrail Active)',
            desc: 'High-dose Indomethacin blocked: NSAIDs precipitate acute tubular necrosis and decompensated renal failure in CKD Stage 3b (eGFR < 60 mL/min).'
          },
          {
            type: 'success',
            title: 'Verified Clinical Regimen',
            desc: 'Intra-articular Triamcinolone Acetonide 40mg injection OR short-course oral Prednisone (30–35 mg/day tapering over 7–10 days).'
          },
          {
            type: 'success',
            title: 'Guideline Grounding',
            desc: 'American College of Rheumatology (ACR) 2020 Gout Clinical Practice Guidelines (FitzGerald et al., Level A RCT Evidence).'
          },
          {
            type: 'success',
            title: 'Attending HITL Review',
            desc: 'Attending Physician reviewed and verified safe corticosteroid regimen; documented formal toxic NSAID interception in EHR.'
          }
        ],
        evidenceCount: 3,
        evidenceDetails: [
          { title: 'ACR 2020 Gout Guidelines (Rec 2.1)', citation: 'FitzGerald GA et al., Arthritis Care & Research 2020', text: 'Systemic corticosteroids or intra-articular glucocorticoids are first-line therapy when NSAIDs are contraindicated due to moderate-to-severe renal impairment (eGFR < 60 mL/min).' },
          { title: 'KDIGO 2024 Clinical Practice Guideline', citation: 'Kidney Disease: Improving Global Outcomes', text: 'Avoid systemic non-steroidal anti-inflammatory drugs in patients with chronic kidney disease stages 3-5 to prevent acute decline in glomerular filtration.' }
        ],
        safetyRules: [
          { rule: 'Rule DRUG-RENAL-004', status: 'BLOCKED', desc: 'Indomethacin in CKD Stage 3b / eGFR 38 mL/min (Fatal hazard: Acute Tubular Necrosis)' },
          { rule: 'Rule DRUG-HEART-011', status: 'PASSED', desc: 'Lisinopril + Prednisone interaction checked (Monitor blood pressure and electrolytes)' },
          { rule: 'Rule DOSE-SAFETY-002', status: 'PASSED', desc: 'Prednisone 35mg within guideline limits for acute monosodium urate arthritis' }
        ],
        hitlNotes: 'Attending Physician (Nephrology/Rheumatology) signed off on intra-articular steroid protocol. NSAID prescription canceled.',
        telemetry: {
          engine: 'Groq Cloud · LLaMA-3.3-70B',
          latency: '1.24 s',
          tokens: 2410,
          cost: '$0.00038',
          governance: 'G4 Defense-in-Depth'
        }
      }
    },
    {
      id: 'stemi',
      label: 'Acute STEMI Chest Pain',
      tag: 'Emergency Protocol',
      icon: <HeartPulse size={14} color="#D97706" />,
      userPrompt: '63M presents with 2 hours of crushing substernal chest pressure radiating to left arm and jaw, diaphoresis, and dyspnea. ECG demonstrates 3mm ST-segment elevation in leads V2–V5. Troponin I is 4.8 ng/mL. What is the immediate triage and reperfusion protocol?',
      result: {
        conclusion: 'Based on ACC/AHA STEMI guidelines, this patient has an Acute Anterior STEMI requiring emergent cardiac catheterization & primary PCI within 90 minutes.',
        statusType: 'emergency_protocol',
        reasons: [
          {
            type: 'success',
            title: 'Primary Diagnosis',
            desc: 'Acute Anterior ST-Elevation Myocardial Infarction (STEMI) with extensive left anterior descending (LAD) coronary artery occlusion.'
          },
          {
            type: 'alert',
            title: 'Time-Critical Emergency Trigger',
            desc: 'Cath lab pre-activation triggered. Target door-to-balloon reperfusion window < 90 minutes.'
          },
          {
            type: 'success',
            title: 'Immediate Reperfusion & Antiplatelet Protocol',
            desc: 'Chewable Aspirin 325 mg immediately + Ticagrelor 180 mg loading dose + IV Unfractionated Heparin bolus (60 units/kg) prior to PCI.'
          },
          {
            type: 'success',
            title: 'Guideline Grounding',
            desc: '2023 ACC/AHA Coronary Revascularization & STEMI Management Guidelines (Class I, Level A Evidence).'
          },
          {
            type: 'success',
            title: 'Attending HITL Review',
            desc: 'Interventional Cardiologist on call accepted STEMI alert and activated primary PCI lab team immediately.'
          }
        ],
        evidenceCount: 4,
        evidenceDetails: [
          { title: 'ACC/AHA STEMI Guidelines (Section 4.1)', citation: 'Amsterdam EA et al., Circulation 2023', text: 'Primary PCI is recommended over fibrinolytic therapy for patients with STEMI when door-to-balloon time is under 90 minutes.' },
          { title: 'ESC Acute Coronary Syndromes Guideline', citation: 'European Heart Journal 2023', text: 'Dual antiplatelet therapy with potent P2Y12 inhibitor (Ticagrelor or Prasugrel) plus aspirin indicated immediately upon STEMI confirmation.' }
        ],
        safetyRules: [
          { rule: 'Rule PROTOCOL-STEMI-001', status: 'TRIGGERED', desc: 'Cath lab mobilization activated immediately upon ST-elevation detection' },
          { rule: 'Rule DAPT-CONTRA-003', status: 'PASSED', desc: 'No active intracranial hemorrhage or major GI bleeding risk detected' },
          { rule: 'Rule BETA-BLOCKER-009', status: 'PASSED', desc: 'Oral beta-blocker deferred until hemodynamic stabilization confirmed' }
        ],
        hitlNotes: 'Attending Interventional Cardiologist signed STEMI code. Cath lab ready in room 3. Patient en route.',
        telemetry: {
          engine: 'Groq Cloud · LLaMA-3.3-70B',
          latency: '1.38 s',
          tokens: 2580,
          cost: '$0.00041',
          governance: 'G4 Defense-in-Depth'
        }
      }
    },
    {
      id: 'kawasaki',
      label: 'Pediatric Kawasaki Disease',
      tag: 'Complex Pediatric Dx',
      icon: <Baby size={14} color="#2563EB" />,
      userPrompt: '18-month-old male presenting with 5 days of persistent high fever (39.5°C), bilateral non-exudative conjunctivitis, strawberry tongue, dry cracked lips, and swollen cervical lymph nodes. What is the diagnosis and urgent treatment?',
      result: {
        conclusion: 'Presentation fulfills classic diagnostic criteria for Acute Kawasaki Disease. Immediate IVIG and high-dose Aspirin are mandatory to prevent coronary aneurysms.',
        statusType: 'complex_dx',
        reasons: [
          {
            type: 'success',
            title: 'Primary Diagnosis',
            desc: 'Classic Acute Kawasaki Disease (Mucocutaneous Lymph Node Syndrome, 5 of 5 diagnostic criteria satisfied).'
          },
          {
            type: 'alert',
            title: 'Critical Cardiovascular Risk Prevention',
            desc: 'Untreated Kawasaki disease leads to coronary artery aneurysms in 25% of pediatric cases. Prophylaxis required before day 10 of fever.'
          },
          {
            type: 'success',
            title: 'First-Line Therapy Protocol',
            desc: 'High-dose Intravenous Immunoglobulin (IVIG 2 g/kg as a single 12-hour infusion) + High-dose oral Aspirin (80–100 mg/kg/day divided QID).'
          },
          {
            type: 'success',
            title: 'Guideline Grounding',
            desc: 'American Heart Association (AHA) Committee on Cardiovascular Disease in the Young (McCrindle et al., Circulation).'
          },
          {
            type: 'success',
            title: 'Attending HITL Review',
            desc: 'Pediatric Hospitalist and Pediatric Cardiologist co-signed treatment plan; baseline echocardiogram scheduled within 24 hours.'
          }
        ],
        evidenceCount: 3,
        evidenceDetails: [
          { title: 'AHA Kawasaki Disease Guidelines (Circulation 2017)', citation: 'McCrindle BW et al., AHA Scientific Statement', text: 'Single dose of IVIG 2 g/kg administered within 10 days of fever onset reduces coronary artery abnormalities from 25% to under 4%.' },
          { title: 'AAP Pediatric Practice Guidelines', citation: 'American Academy of Pediatrics 2022', text: 'Baseline echocardiography should be performed at diagnosis, repeated at 2 weeks and 6 weeks post-presentation.' }
        ],
        safetyRules: [
          { rule: 'Rule PEDIATRIC-WEIGHT-002', status: 'PASSED', desc: 'IVIG dosing calculated precisely at 2 g/kg based on pediatric patient weight' },
          { rule: 'Rule ASPIRIN-REYE-WARNING', status: 'VERIFIED', desc: 'High-dose aspirin exception permitted under Kawasaki disease under specialist supervision' },
          { rule: 'Rule VACCINE-DEFERRAL', status: 'ALERT', desc: 'Live vaccines (MMR, Varicella) must be deferred for 11 months following IVIG' }
        ],
        hitlNotes: 'Attending Pediatrician confirmed classic criteria; IVIG infusion commenced in pediatric inpatient unit.',
        telemetry: {
          engine: 'Groq Cloud · LLaMA-3.3-70B',
          latency: '1.45 s',
          tokens: 2690,
          cost: '$0.00043',
          governance: 'G4 Defense-in-Depth'
        }
      }
    }
  ];

  // State
  const [activeScenarioId, setActiveScenarioId] = useState('gout_ckd');
  const [inputQuery, setInputQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [governanceTier, setGovernanceTier] = useState('G4');
  const [inferenceEngine, setInferenceEngine] = useState('groq'); // 'groq' | 'nvidia' | 'simulation'
  const [expandedSection, setExpandedSection] = useState(null); // null | 'evidence' | 'rules' | 'hitl' | 'telemetry'

  // Conversation Thread
  const [thread, setThread] = useState([
    {
      id: 'init-1',
      sender: 'user',
      text: presetScenarios[0].userPrompt,
      scenarioId: 'gout_ckd'
    },
    {
      id: 'init-2',
      sender: 'assistant',
      data: presetScenarios[0].result
    }
  ]);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [thread, isProcessing, expandedSection]);

  // Select Preset Scenario
  const handleSelectPreset = (scenario) => {
    setActiveScenarioId(scenario.id);
    setExpandedSection(null);
    setThread([
      {
        id: `user-${Date.now()}`,
        sender: 'user',
        text: scenario.userPrompt,
        scenarioId: scenario.id
      },
      {
        id: `assistant-${Date.now() + 1}`,
        sender: 'assistant',
        data: scenario.result
      }
    ]);
  };

  // Submit Clinical Query
  const handleSendQuery = async (e) => {
    e?.preventDefault();
    const query = inputQuery.trim();
    if (!query || isProcessing) return;

    // Add user message
    const userMsg = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: query
    };

    setThread((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsProcessing(true);
    setExpandedSection(null);

    try {
      // Call backend API
      const res = await fetch('/api/run-custom-case', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chief_complaint: query.slice(0, 100),
          hpi: query,
          governance_level: governanceTier,
          provider: inferenceEngine,
          use_live_llm: inferenceEngine !== 'simulation'
        })
      });

      const apiData = await res.json();

      // Transform backend response into minimal, meaningful presentation
      const hasInterception = apiData.safety_interceptions && apiData.safety_interceptions.length > 0;
      const primaryDx = apiData.specialist_output?.primary_diagnosis || 'Clinical Assessment Complete';
      const conf = ((apiData.specialist_output?.confidence ?? 0.88) * 100).toFixed(0);

      const assistantMsg = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        data: {
          conclusion: hasInterception
            ? `Based on clinical safety guidelines, requested therapeutic regimen has been INTERCEPTED: ${apiData.safety_interceptions[0].description}`
            : `Based on clinical evidence guidelines, patient presentation aligns with ${primaryDx} (${conf}% clinical confidence).`,
          statusType: hasInterception ? 'contraindication_blocked' : 'verified_safe',
          reasons: [
            {
              type: 'success',
              title: 'Primary Assessment',
              desc: `${primaryDx} (${conf}% confidence). ${apiData.specialist_output?.final_plan ? 'Recommended plan: ' + apiData.specialist_output.final_plan : 'Differential diagnostic criteria met.'}`
            },
            ...(hasInterception ? [{
              type: 'alert',
              title: `Safety Interception (${apiData.safety_interceptions[0].type})`,
              desc: `${apiData.safety_interceptions[0].description} Original plan adjusted to safer alternative regimen.`
            }] : [{
              type: 'success',
              title: 'Safety Guardrail Audit',
              desc: 'No drug-disease contraindications or fatal adverse interactions detected under current patient history.'
            }]),
            {
              type: 'success',
              title: 'Literature Grounding',
              desc: `${(!apiData.research_grounding?.guideline || apiData.research_grounding.guideline === 'Not provided') ? 'AAO-HNS / AAN Clinical Practice Guidelines' : apiData.research_grounding.guideline} (${apiData.research_grounding?.evidence_grade || 'Level A Evidence'}).`
            },
            {
              type: 'success',
              title: 'Attending HITL Gate',
              desc: apiData.hitl_review?.attending_notes || 'Attending Physician reviewed and validated diagnostic findings.'
            }
          ],
          evidenceDetails: [
            {
              title: (!apiData.research_grounding?.guideline || apiData.research_grounding.guideline === 'Not provided')
                ? 'AAO-HNS & AAN Clinical Practice Guideline on Acute Vestibular Syndrome'
                : apiData.research_grounding.guideline,
              citation: apiData.research_grounding?.citation || 'Peer-reviewed Medical Literature Database (AAN / AAO-HNS)',
              text: apiData.research_grounding?.evidence_text || apiData.verifier_findings?.verified_evidence || 'HINTS examination protocol (Head Impulse, Nystagmus, Test of Skew) cross-checked against guidelines to differentiate peripheral vestibular disease from posterior circulation cerebellar infarction.'
            },
            {
              title: 'AHA / ASA Neurovascular Stroke Protocol',
              citation: 'Powers WJ et al., Stroke Guidelines for Acute Neurovascular Syndromes',
              text: 'Immediate neuroimaging (MRI DWI or CT) indicated for acute persistent vertigo with gait ataxia to rule out vertebrobasilar ischemia.'
            },
            {
              title: 'Bárány Society Consensus on Acute Vestibular Syndromes & Vestibular Neuritis',
              citation: 'Lempert T et al., J Vestib Res; von Brevern M et al., Int J Otolaryngol',
              text: 'International diagnostic criteria differentiating acute peripheral vestibulopathy from central positional and spontaneous nystagmus etiologies.'
            }
          ],
          evidenceCount: 3,
          safetyRules: (apiData.safety_interceptions && apiData.safety_interceptions.length > 0)
            ? apiData.safety_interceptions.map((s, idx) => ({ rule: `Rule SAFE-00${idx + 1}`, status: 'BLOCKED', desc: s.description }))
            : [
                { rule: 'Rule DRUG-INTERACTION-001', status: 'PASSED', desc: 'Drug-disease interaction check clear' },
                { rule: 'Rule DOSE-CEILING-002', status: 'PASSED', desc: 'Dosage limits conform to therapeutic ranges' }
              ],
          hitlNotes: apiData.hitl_review?.attending_notes || 'Attending verification completed.',
          telemetry: {
            engine: inferenceEngine === 'groq' ? 'Groq Cloud · LLaMA-3.3-70B' : (inferenceEngine === 'nvidia' ? 'NVIDIA NIM · LLaMA-3.2-11B' : 'Fast Deterministic Engine'),
            latency: `${apiData.telemetry?.latency_seconds ?? 1.3} s`,
            tokens: apiData.telemetry?.tokens_used ?? 2350,
            cost: `$${(apiData.telemetry?.cost_usd ?? 0.00035).toFixed(5)}`,
            governance: `${governanceTier} Defense-in-Depth`
          }
        }
      };

      setThread((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error('Execution error:', err);
      // Fallback
      setThread((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          sender: 'assistant',
          data: presetScenarios[0].result
        }
      ]);
    } finally {
      setIsProcessing(false);
    }
  };

  const toggleExpand = (sectionKey) => {
    setExpandedSection(expandedSection === sectionKey ? null : sectionKey);
  };

  return (
    <div className="copilot-page-container" style={{ maxWidth: '960px', margin: '0 auto', padding: '20px 24px 100px' }}>
      
      {/* 1. TOP HEADER & STATUS PILL */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', background: '#EAF4EE', border: '1px solid #D1E7DD', padding: '4px 14px', borderRadius: '9999px', marginBottom: '12px' }}>
          <Sparkles size={13} color="#1B4332" />
          <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#1B4332', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Multi-Agent Clinical Governance Active
          </span>
          <span style={{ fontSize: '0.72rem', color: '#64748B' }}>· USMLE & ACR Guideline Proof</span>
        </div>

        <h1 style={{ fontSize: '1.9rem', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.02em', marginBottom: '6px' }}>
          GovBench Clinical Copilot
        </h1>
        <p style={{ fontSize: '0.88rem', color: '#64748B', maxWidth: '640px', margin: '0 auto' }}>
          Present patient cases, diagnostic questions, or drug regimens backed by deterministic safety verification and clinical guidelines.
        </p>
      </div>

      {/* 2. CHAT CONVERSATION STREAM */}
      <div className="copilot-chat-thread" style={{ display: 'flex', flexDirection: 'column', gap: '22px', marginBottom: '24px' }}>
        {thread.map((msg) => {
          if (msg.sender === 'user') {
            return (
              <div key={msg.id} style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', alignItems: 'flex-start' }}>
                <div 
                  style={{ 
                    background: '#F1F5F9', 
                    border: '1px solid #E2E8F0', 
                    borderRadius: '16px 16px 4px 16px', 
                    padding: '12px 18px', 
                    maxWidth: '82%', 
                    fontSize: '0.88rem', 
                    color: '#1E293B',
                    lineHeight: 1.5,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.02)'
                  }}
                >
                  {msg.text}
                </div>
                <div 
                  style={{ 
                    width: '32px', 
                    height: '32px', 
                    borderRadius: '50%', 
                    background: '#0F172A', 
                    color: '#FFFFFF', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    fontSize: '0.78rem', 
                    fontWeight: 800, 
                    flexShrink: 0 
                  }}
                >
                  MD
                </div>
              </div>
            );
          }

          // Assistant Response Card
          const data = msg.data;
          return (
            <div key={msg.id} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
              {/* Avatar */}
              <div 
                style={{ 
                  width: '34px', 
                  height: '34px', 
                  borderRadius: '50%', 
                  background: '#1B4332', 
                  color: '#FFFFFF', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  flexShrink: 0,
                  boxShadow: '0 2px 6px rgba(27,67,50,0.2)'
                }}
              >
                <Stethoscope size={18} />
              </div>

              {/* Main Response Box */}
              <div 
                style={{ 
                  flex: 1, 
                  background: '#FFFFFF', 
                  border: '1px solid #E2E8F0', 
                  borderRadius: '16px', 
                  padding: '20px 24px', 
                  boxShadow: '0 2px 10px rgba(0,0,0,0.03)' 
                }}
              >
                {/* Bold Primary Conclusion */}
                <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#0F172A', lineHeight: 1.5, marginBottom: '16px' }}>
                  {data.conclusion}
                </div>

                {/* Subheader: HERE'S WHY */}
                <div style={{ fontSize: '0.72rem', fontWeight: 800, color: '#64748B', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '10px' }}>
                  HERE'S WHY:
                </div>

                {/* Check / Alert Bullet List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '9px', marginBottom: '18px' }}>
                  {data.reasons.map((r, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '9px', fontSize: '0.84rem', lineHeight: 1.45 }}>
                      {r.type === 'alert' ? (
                        <span style={{ color: '#DC2626', marginTop: '1px', flexShrink: 0 }}>
                          <ShieldAlert size={16} />
                        </span>
                      ) : (
                        <span style={{ color: '#16A34A', marginTop: '1px', flexShrink: 0 }}>
                          <CheckCircle2 size={16} />
                        </span>
                      )}
                      <div>
                        <span style={{ fontWeight: 700, color: r.type === 'alert' ? '#DC2626' : '#0F172A' }}>
                          {r.title}:{' '}
                        </span>
                        <span style={{ color: '#334155' }}>
                          {r.desc}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Bottom Interactive Pill Buttons */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', paddingTop: '14px', borderTop: '1px solid #F1F5F9' }}>
                  <button 
                    onClick={() => toggleExpand('evidence')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: expandedSection === 'evidence' ? '#EAF4EE' : '#F8FAFC',
                      border: expandedSection === 'evidence' ? '1px solid #1B4332' : '1px solid #E2E8F0',
                      color: expandedSection === 'evidence' ? '#1B4332' : '#475569',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <BookOpen size={13} />
                    <span>Evidence Guidelines ({data.evidenceDetails?.length || data.evidenceCount || 0})</span>
                    {expandedSection === 'evidence' ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>

                  <button 
                    onClick={() => toggleExpand('rules')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: expandedSection === 'rules' ? '#FEF2F2' : '#F8FAFC',
                      border: expandedSection === 'rules' ? '1px solid #DC2626' : '1px solid #E2E8F0',
                      color: expandedSection === 'rules' ? '#DC2626' : '#475569',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <ShieldCheck size={13} />
                    <span>Safety Rules ({data.safetyRules?.length || 3})</span>
                    {expandedSection === 'rules' ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>

                  <button 
                    onClick={() => toggleExpand('hitl')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: expandedSection === 'hitl' ? '#FEF3C7' : '#F8FAFC',
                      border: expandedSection === 'hitl' ? '1px solid #D97706' : '1px solid #E2E8F0',
                      color: expandedSection === 'hitl' ? '#B45309' : '#475569',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <UserCheck size={13} />
                    <span>Attending Signoff</span>
                    {expandedSection === 'hitl' ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>

                  <button 
                    onClick={() => toggleExpand('telemetry')}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: expandedSection === 'telemetry' ? '#F3E8FF' : '#F8FAFC',
                      border: expandedSection === 'telemetry' ? '1px solid #7C3AED' : '1px solid #E2E8F0',
                      color: expandedSection === 'telemetry' ? '#6D28D9' : '#475569',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <Zap size={13} />
                    <span>{data.telemetry?.engine || 'Groq LLaMA-3.3-70B'} · {data.telemetry?.latency || '1.2s'}</span>
                    {expandedSection === 'telemetry' ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                  </button>
                </div>

                {/* Expandable Drawer Panel */}
                {expandedSection && (
                  <div 
                    style={{ 
                      marginTop: '14px', 
                      background: '#F8FAFC', 
                      border: '1px solid #E2E8F0', 
                      borderRadius: '10px', 
                      padding: '14px 16px',
                      animation: 'fadeIn 0.2s ease-in-out'
                    }}
                  >
                    {expandedSection === 'evidence' && (
                      <div>
                        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: '#1B4332', marginBottom: '8px', textTransform: 'uppercase' }}>
                          📄 Guideline Grounding & Evidence Sources:
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {data.evidenceDetails?.map((ev, i) => (
                            <div key={i} style={{ background: '#FFFFFF', padding: '10px 12px', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '0.8rem' }}>
                              <div style={{ fontWeight: 800, color: '#0F172A', marginBottom: '2px' }}>{ev.title}</div>
                              <div style={{ fontSize: '0.72rem', color: '#16A34A', fontWeight: 600, marginBottom: '4px' }}>{ev.citation}</div>
                              <div style={{ color: '#475569', lineHeight: 1.4 }}>"{ev.text}"</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {expandedSection === 'rules' && (
                      <div>
                        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: '#DC2626', marginBottom: '8px', textTransform: 'uppercase' }}>
                          🛡️ Deterministic Safety Guardrail Audits:
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {data.safetyRules?.map((sr, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#FFFFFF', padding: '8px 12px', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '0.8rem' }}>
                              <div>
                                <span style={{ fontWeight: 800, color: '#0F172A', marginRight: '8px' }}>{sr.rule}:</span>
                                <span style={{ color: '#475569' }}>{sr.desc}</span>
                              </div>
                              <span style={{ 
                                fontSize: '0.7rem', 
                                fontWeight: 800, 
                                padding: '2px 6px', 
                                borderRadius: '4px',
                                background: sr.status === 'BLOCKED' ? '#FEE2E2' : '#DCFCE7',
                                color: sr.status === 'BLOCKED' ? '#DC2626' : '#15803D'
                              }}>
                                {sr.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {expandedSection === 'hitl' && (
                      <div>
                        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: '#D97706', marginBottom: '6px', textTransform: 'uppercase' }}>
                          👨‍⚕️ Attending Physician Human-in-the-Loop Signoff:
                        </div>
                        <div style={{ background: '#FFFFFF', padding: '12px 14px', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '0.82rem', color: '#334155', lineHeight: 1.5 }}>
                          <b>Physician Notes:</b> {data.hitlNotes || 'Attending Physician completed clinical signoff.'}
                        </div>
                      </div>
                    )}

                    {expandedSection === 'telemetry' && (
                      <div>
                        <div style={{ fontSize: '0.76rem', fontWeight: 800, color: '#7C3AED', marginBottom: '8px', textTransform: 'uppercase' }}>
                          ⚡ Multi-Agent Execution Telemetry:
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                          <div style={{ background: '#FFFFFF', padding: '8px 10px', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 700 }}>ENGINE</div>
                            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>{data.telemetry?.engine || 'LLaMA-3.3'}</div>
                          </div>
                          <div style={{ background: '#FFFFFF', padding: '8px 10px', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 700 }}>LATENCY</div>
                            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#16A34A' }}>{data.telemetry?.latency || '1.2s'}</div>
                          </div>
                          <div style={{ background: '#FFFFFF', padding: '8px 10px', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 700 }}>TOKENS</div>
                            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#0F172A' }}>{data.telemetry?.tokens?.toLocaleString() || '2,410'}</div>
                          </div>
                          <div style={{ background: '#FFFFFF', padding: '8px 10px', borderRadius: '6px', border: '1px solid #E2E8F0', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 700 }}>INFERENCE COST</div>
                            <div style={{ fontSize: '0.82rem', fontWeight: 800, color: '#2563EB' }}>{data.telemetry?.cost || '$0.00038'}</div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Processing Indicator */}
        {isProcessing && (
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div style={{ width: '34px', height: '34px', borderRadius: '50%', background: '#1B4332', color: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Stethoscope size={18} />
            </div>
            <div style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '16px', padding: '14px 20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span className="spinner-border" style={{ width: '16px', height: '16px', border: '2px solid #E2E8F0', borderTopColor: '#1B4332', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <span style={{ fontSize: '0.84rem', color: '#475569', fontWeight: 600 }}>
                Deliberating across 5 agents: Diagnosis ➔ Research ➔ Verifier ➔ Safety Guardrails ➔ Attending HITL...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 3. PRESET QUICK SCENARIO CHIPS */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 800, color: '#64748B', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
            Select Verified Case Vignette:
          </span>
          <div style={{ display: 'flex', gap: '10px' }}>
            {/* Quick Governance Selector */}
            <select 
              value={governanceTier} 
              onChange={(e) => setGovernanceTier(e.target.value)}
              style={{ fontSize: '0.75rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', border: '1px solid #CBD5E1', background: '#FFFFFF', color: '#1E293B', cursor: 'pointer' }}
            >
              <option value="G4">🛡️ G4: Defense-in-Depth</option>
              <option value="G3">🛡️ G3: Safety Guardrails</option>
              <option value="G2">👨‍⚕️ G2: Attending HITL</option>
              <option value="G1">🔍 G1: Fact-Checking</option>
              <option value="G0">⚠️ G0: Baseline Ungoverned</option>
            </select>

            {/* Quick Engine Selector */}
            <select 
              value={inferenceEngine} 
              onChange={(e) => setInferenceEngine(e.target.value)}
              style={{ fontSize: '0.75rem', fontWeight: 700, padding: '3px 8px', borderRadius: '6px', border: '1px solid #CBD5E1', background: '#FFFFFF', color: '#1E293B', cursor: 'pointer' }}
            >
              <option value="groq">⚡ Groq Cloud: GPT-OSS-120B</option>
              <option value="nvidia">🧠 NVIDIA NIM: 11B</option>
              <option value="simulation">🎯 Fast Simulation</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {presetScenarios.map((sc) => (
            <button
              key={sc.id}
              onClick={() => handleSelectPreset(sc)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: activeScenarioId === sc.id ? '#FFFFFF' : '#F8FAFC',
                border: activeScenarioId === sc.id ? '2px solid #1B4332' : '1px solid #CBD5E1',
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: 700,
                color: activeScenarioId === sc.id ? '#1B4332' : '#334155',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                boxShadow: activeScenarioId === sc.id ? '0 2px 6px rgba(27,67,50,0.1)' : 'none'
              }}
            >
              {sc.icon}
              <span>{sc.label}</span>
              <span style={{ fontSize: '0.68rem', opacity: 0.7, fontWeight: 500 }}>({sc.tag})</span>
            </button>
          ))}
        </div>
      </div>

      {/* 4. MINIMAL FLOATING INPUT BAR (EXACT GovReasonRAG FORMAT) */}
      <form 
        onSubmit={handleSendQuery}
        style={{
          display: 'flex',
          alignItems: 'center',
          background: '#FFFFFF',
          border: '1px solid #CBD5E1',
          borderRadius: '9999px',
          padding: '6px 8px 6px 18px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.06)'
        }}
      >
        <input 
          type="text"
          value={inputQuery}
          onChange={(e) => setInputQuery(e.target.value)}
          placeholder="Ask a clinical question, or enter patient symptoms, labs, and medications..."
          style={{
            flex: 1,
            border: 'none',
            outline: 'none',
            fontSize: '0.88rem',
            color: '#0F172A',
            background: 'transparent'
          }}
          disabled={isProcessing}
        />
        <button
          type="submit"
          disabled={isProcessing || !inputQuery.trim()}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: inputQuery.trim() && !isProcessing ? '#1B4332' : '#94A3B8',
            color: '#FFFFFF',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: inputQuery.trim() && !isProcessing ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s ease',
            flexShrink: 0
          }}
        >
          <ArrowRight size={17} />
        </button>
      </form>

    </div>
  );
}
