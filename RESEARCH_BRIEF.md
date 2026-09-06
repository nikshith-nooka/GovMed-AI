# Comprehensive System Blueprint & Literature Positioning
# Project: Quantifying the Governance-Cost Tradeoff in Multi-Agent Clinical Diagnosis Systems

---

## 1. Project Clarification & Scope
- **What this project IS:**
  - An academic **Research Benchmark System** and **Evaluation Harness**
  - A **Multi-Agent Governance Simulator** measuring quality, safety, latency, and token overhead
  - A **Cost-Quality-Safety Analysis Framework** generating empirical Pareto frontiers
  - A publishable, reproducible experimental study for IEEE/ACL/NeurIPS/JAMIA formats
  - A lightweight **Streamlit Research Demo UI** for presentations and GitHub demonstrations

- **What this project is NOT:**
  - NOT an "AI doctor" or patient-facing diagnostic tool
  - NOT a hospital production electronic health record (EHR) integration
  - NOT medical advice or clinical decision software intended for unvetted deployment

---

## 2. Competitive Positioning: How This Study Beats Existing Work

| Existing Literature | Their Contribution | Our Novel Extension & Competitive Advantage |
| :--- | :--- | :--- |
| **MedAgentBoard** ([arXiv:2505.12371](https://arxiv.org/abs/2505.12371)) | Benchmarks multi-agent collaboration vs. single-LLM across medical tasks. | Benchmarks **Governance Layers** (verifiers, validators, HITL) rather than just agent teams. |
| **Optimization Paradox in Clinical AI** ([arXiv:2506.06574](https://arxiv.org/abs/2506.06574)) | Shows component optimization can backfire system-wide (Best-of-Breed paradox). | Reveals **which specific governance layers yield the best system-wide ROI** and where diminishing returns hit. |
| **ClinicalAgents** ([arXiv:2603.26182](https://arxiv.org/abs/2603.26182)) | MCTS-based dynamic agent orchestration with Dual-Memory. | Adds **pluggable governance modules** with empirical cost, token, and latency instrumentation. |
| **MeDxAgent / MeDxBench** ([arXiv:2606.03416](https://arxiv.org/abs/2606.03416) / [nec-research/meddxagent](https://github.com/nec-research/meddxagent)) | Modular interactive differential diagnosis consultation system. | Integrates **Verifier + HITL + Safety Validator** with rigorous 5-variant ablation study. |
| **GraphDx** ([ACL Findings 2026](https://aclanthology.org/2026.findings-acl.1092/)) | Cost-aware diagnosis focused on patient test expenditure. | Measures **AI Governance Overhead** (LLM prompt/output tokens, inference latency, simulated physician burden). |

---

## 3. The 7 Specialized Agents
Each agent is implemented with prompt-engineered clinical personas compatible with free/open-weight LLM backends (Groq Llama-3.3-70B, Google Gemini 2.5/Flash, OpenRouter, Cerebras):

1. **Research Agent:** Extracts patient history, physical findings, lab results, and risk factors from raw clinical notes.
2. **Diagnosis Agent:** Generates prioritized differential diagnoses (Top-$k$) with pathophysiological justifications.
3. **Report Agent:** Synthesizes structured clinical documentation (SOAP format / diagnostic assessment plan).
4. **Verifier Agent:** Cross-references diagnostic claims against the raw source clinical vignette to catch ungrounded assertions.
5. **Safety Validator Agent:** Checks for contraindications, drug interactions, missed red flags, and critical clinical safety rules.
6. **HITL Simulator Agent:** Simulates an attending physician review gate (risk-stratified approval, critique, or rejection).
7. **Consistency Checker Agent:** Ensures logical coherence between differential ranking, symptoms, and recommended next steps.

---

## 4. Pluggable Governance Framework: 5 Pipeline Variants for Ablation

```
[Clinical Case / Raw Vignette]
       │
       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ V1: Baseline (Ungoverned)                                                       │
│ Research Agent ───► Diagnosis Agent ───► Report Agent                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│ V2: Verifier Governance                                                         │
│ Research Agent ───► Diagnosis Agent ───► Verifier Agent ───► Report Agent       │
├─────────────────────────────────────────────────────────────────────────────────┤
│ V3: HITL Governance                                                             │
│ Research Agent ───► Diagnosis Agent ───► HITL Simulator Gate ───► Report Agent  │
├─────────────────────────────────────────────────────────────────────────────────┤
│ V4: Safety Validator Governance                                                 │
│ Research Agent ───► Diagnosis Agent ───► Safety Validator ───► Report Agent     │
├─────────────────────────────────────────────────────────────────────────────────┤
│ V5: Full Governance (Tiered Defense-in-Depth)                                   │
│ Research ──► Diagnosis ──► Verifier ──► Safety Validator ──► HITL ──► Report    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Automated Benchmark Harness
- **Dataset Integration:** [MedQA / USMLE](https://huggingface.co/datasets/bigbio/med_qa) clinical vignettes + curated complex clinical cases.
- **Matrix Testing:** e.g., $N$ clinical cases $\times$ 5 pipeline variants $\times$ multi-model backends (Groq, Gemini, DeepSeek).
- **Execution Telemetry Logged Per Run:**
  - `case_id`, `variant_id`, `model_backend`
  - `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`
  - `latency_ms` per agent and total end-to-end
  - `financial_cost_usd` computed from provider rate cards
  - Full intermediate agent thought chains and governance interventions

---

## 6. Comprehensive Evaluation Engine
1. **Exact Answer / Gold Diagnosis Match:** Top-1 and Top-3 accuracy against benchmark labels.
2. **Semantic Diagnostic Alignment:** Embedding / clinical ontology similarity for alternative phrasing.
3. **Rubric-Based Quality Scoring:** Multi-attribute rubric (completeness, diagnostic reasoning, differential coverage).
4. **LLM-as-a-Judge:** Free-tier judge (Gemini 2.5 Flash or Groq Llama-3.3-70B) executing standardized medical grading prompts.
5. **Hallucination Detection:** Fact-checking claims against input notes (identifying phantom labs or false patient history).
6. **Safety Violation Index:** Quantifying missed contraindications, dangerous discharge advice, or fatal oversights.
7. **Report Completeness Score:** Assessment of SOAP structure adherence.

---

## 7. Streamlit Research UI Architecture (4 Pages)
1. **Interactive Single Case Runner:**
   - Input custom or preset clinical note $\rightarrow$ Choose pipeline variant $\rightarrow$ Watch real-time agent execution with inspection of intermediate critique/corrections.
2. **Side-by-Side Variant Comparison:**
   - Run V1 through V5 on the same case side-by-side with diff viewers showing how governance prevented errors.
3. **Governance-Cost Benchmark Analytics:**
   - Interactive Pareto frontier plots: Quality vs. Token Cost, Quality vs. Latency, Hallucination Rate vs. Governance Level.
4. **Case Explorer & Error Analysis:**
   - Drilldown into failed cases, safety flags, and marginal ROI metrics.
