"""Unified LLM Client supporting Groq, Gemini, OpenRouter, and Deterministic Mock."""

from __future__ import annotations

import itertools
import os
import time
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import httpx
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    estimated_cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)


class LiveInferenceUnavailable(RuntimeError):
    """Raised instead of substituting simulated output when allow_mock_fallback=False."""


# Provider names that select the deterministic offline demo generator (not an AI model).
DEMO_PROVIDERS = ("mock", "simulation", "offline", "demo")
DEMO_PROVIDER_LABEL = "Offline demo (not AI)"


class UnifiedLLMClient:
    _key_cursor = itertools.count()

    """Unified LLM client with automatic fallbacks and offline simulation mode."""

    # Pricing per 1M tokens in USD
    PRICING_TABLE = {
        "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
        "openai/gpt-oss-20b": {"input": 0.075, "output": 0.30},
        "meta/llama-3.3-70b-instruct": {"input": 0.59, "output": 0.79},
        "meta/llama-3.2-11b-vision-instruct": {"input": 0.10, "output": 0.20},
        "nvidia/llama-3.1-nemotron-70b-instruct": {"input": 0.50, "output": 0.80},
        "qwen/qwen3.8-27b": {"input": 0.80, "output": 4.00},
        "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
        "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
        "gemini-flash-latest": {"input": 0.075, "output": 0.30},
        "clinical-mock-v1": {"input": 0.59, "output": 0.79},
    }

    def __init__(
        self,
        provider: str = "groq",
        model: Optional[str] = None,
        force_mock: bool = False,
        timeout_seconds: float = 45.0,
        allow_mock_fallback: bool = True,
        reasoning_effort: Optional[str] = None,
    ):
        self.provider = provider.lower()
        # "low" | "medium" | "high" for reasoning models on Groq (gpt-oss); fewer reasoning tokens = faster.
        self.reasoning_effort = reasoning_effort
        self.force_mock = force_mock
        self.timeout_seconds = timeout_seconds
        # False = raise instead of silently answering with simulated output (use for clinical UI and benchmarks).
        self.allow_mock_fallback = allow_mock_fallback
        self.mock_fallbacks = 0
        # Optional callable(event_dict) told about every provider rate-limit wait, so a UI can show it live.
        self.rate_limit_listener = None
        self.rate_limit_waits = 0
        self.rate_limit_wait_s = 0.0

        # Strict callers (benchmarks, experiments) must never be handed the demo generator by name.
        if self.provider in DEMO_PROVIDERS and not force_mock and not allow_mock_fallback:
            raise LiveInferenceUnavailable(
                f"'{self.provider}' is the {DEMO_PROVIDER_LABEL} generator; strict runs require a live provider.")

        # Configure provider specific endpoints and keys
        if self.provider == "groq":
            groq_keys_str = os.getenv("GROQ_API_KEYS", "").strip()
            if groq_keys_str:
                self.groq_keys = [k.strip() for k in groq_keys_str.split(",") if k.strip()]
            else:
                single_key = os.getenv("GROQ_API_KEY", "").strip()
                self.groq_keys = [single_key] if single_key else []
            self.current_key_idx = 0
            self.api_key = self.groq_keys[0] if self.groq_keys else ""
            self.base_url = "https://api.groq.com/openai/v1/chat/completions"
            self.default_model = "openai/gpt-oss-120b" if (not model or "llama" in (model or "").lower()) else model
            logger.info(f"Initialized Groq client with model={self.default_model} and {len(self.groq_keys)} pooled API key(s).")

        elif self.provider in ("nvidia", "nim"):
            nvidia_keys_str = os.getenv("NVIDIA_API_KEYS", "").strip()
            if nvidia_keys_str:
                self.nvidia_keys = [k.strip() for k in nvidia_keys_str.split(",") if k.strip()]
            else:
                single_key = os.getenv("NVIDIA_API_KEY", "").strip()
                self.nvidia_keys = [single_key] if single_key else []
            self.current_key_idx = 0
            self.api_key = self.nvidia_keys[0] if self.nvidia_keys else ""
            self.base_url = "https://integrate.api.nvidia.com/v1/chat/completions"
            self.default_model = model or "meta/llama-3.2-11b-vision-instruct"
            logger.info(f"Initialized NVIDIA NIM client with {len(self.nvidia_keys)} API key(s).")
        elif self.provider == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.default_model = model or "gemini-flash-latest"
        elif self.provider == "openrouter":
            self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            self.base_url = "https://openrouter.ai/api/v1/chat/completions"
            self.default_model = model or "meta-llama/llama-3.3-70b-instruct:free"
        else:
            self.api_key = ""
            self.base_url = ""
            self.default_model = model or "clinical-mock-v1"
            self.force_mock = True

        # If key is missing, automatically fallback to mock mode with warning
        if not self.api_key and not self.force_mock and not self.allow_mock_fallback:
            raise LiveInferenceUnavailable(f"No API key configured for provider '{self.provider}'.")
        if not self.api_key and not self.force_mock:
            logger.warning(
                f"No API key found for provider '{self.provider}'. "
                f"Falling back to high-fidelity clinical simulation mock mode."
            )
            self.force_mock = True

    def _notify_rate_limit(self, wait_s: float, attempt: int, max_attempts: int) -> None:
        self.rate_limit_waits += 1
        self.rate_limit_wait_s += wait_s
        if self.rate_limit_listener is None:
            return
        try:
            self.rate_limit_listener({"type": "rate_limit", "provider": self.provider, "wait_s": wait_s,
                                      "attempt": attempt, "max_attempts": max_attempts, "at": time.time()})
        except Exception:  # a broken listener must never break inference
            logger.exception("Rate-limit listener failed")

    # Optional sampling seed forwarded with every request (set by the benchmark runner's --seed).
    seed: Optional[int] = None

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self.PRICING_TABLE.get(model, {"input": 0.50, "output": 0.80})
        cost = (prompt_tokens / 1_000_000 * rates["input"]) + (
            completion_tokens / 1_000_000 * rates["output"]
        )
        return round(cost, 6)

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        model_override: Optional[str] = None,
    ) -> LLMResponse:
        """Synchronous chat completion."""
        target_model = model_override or self.default_model

        if self.force_mock:
            return self._mock_generate(messages, target_model)

        # Smooth pacing for providers with strict per-minute RPM (e.g. Gemini 15 RPM = 1 call per 4s)
        if self.provider == "gemini":
            time.sleep(3.2)

        start_time = time.time()
        # Round-robin across pooled keys; the cursor is process-wide so separate requests
        # (each with a fresh client) spread load instead of all starting on key 0.
        key_idx = 0
        if self.provider == "groq" and self.groq_keys:
            key_idx = next(UnifiedLLMClient._key_cursor) % len(self.groq_keys)
            active_key = self.groq_keys[key_idx]
        elif self.provider in ("nvidia", "nim") and getattr(self, "nvidia_keys", None):
            key_idx = next(UnifiedLLMClient._key_cursor) % len(self.nvidia_keys)
            active_key = self.nvidia_keys[key_idx]
        else:
            active_key = self.api_key
        headers = {
            "Authorization": f"Bearer {active_key}",
            "Content-Type": "application/json",
        }
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/govbench-clinical"
            headers["X-Title"] = "GovBench-Clinical"

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        # OpenAI-compatible providers accept a best-effort sampling seed; it does not guarantee determinism.
        if self.seed is not None:
            payload["seed"] = int(self.seed)
        if self.reasoning_effort and self.provider == "groq" and "gpt-oss" in target_model:
            payload["reasoning_effort"] = self.reasoning_effort

        max_retries = 10
        last_exception = None

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(self.base_url, headers=headers, json=payload)
                    if resp.status_code == 429:
                        raw_retry = float(resp.headers.get("retry-after", 6 if self.provider == "gemini" else 2))
                        retry_after = min(max(int(raw_retry), 6 if self.provider == "gemini" else 2), 30)
                        last_exception = RuntimeError(f"rate limited (HTTP 429) by {self.provider}: {resp.text[:200]}")

                        # Rotate once through pooled Groq keys, then wait for the quota window.
                        pool = len(self.groq_keys) if self.provider == "groq" else 0
                        if pool > 1 and (attempt + 1) % pool != 0:
                            key_idx = (key_idx + 1) % pool
                            headers["Authorization"] = f"Bearer {self.groq_keys[key_idx]}"
                            logger.info(f"Groq limit on key: swapping to pooled API key #{key_idx + 1}/{pool}...")
                            time.sleep(1)
                            continue
                        
                        logger.warning(f"Rate limited by {self.provider} (429). Waiting {retry_after}s for quota reset... (attempt {attempt+1}/{max_retries})")
                        self._notify_rate_limit(retry_after, attempt + 1, max_retries)
                        time.sleep(retry_after)
                        continue

                    if resp.status_code != 200:
                        logger.warning(f"HTTP {resp.status_code} from {self.provider}: {resp.text[:300]}")
                    if 400 <= resp.status_code < 500:
                        last_exception = RuntimeError(f"HTTP {resp.status_code} from {self.provider}: {resp.text[:200]}")
                        break
                    resp.raise_for_status()
                    data = resp.json()

                latency_ms = round((time.time() - start_time) * 1000, 2)
                choice = data["choices"][0]
                content = choice["message"].get("content") or ""
                if not content.strip():
                    raise RuntimeError(f"empty completion (finish_reason={choice.get('finish_reason')})")
                usage = data.get("usage") or {}
                p_tokens = usage.get("prompt_tokens") or int(len(str(messages)) / 4)
                c_tokens = usage.get("completion_tokens") or int(len(content) / 4)
                t_tokens = usage.get("total_tokens") or p_tokens + c_tokens
                cost = self.calculate_cost(target_model, p_tokens, c_tokens)

                return LLMResponse(
                    content=content,
                    prompt_tokens=p_tokens,
                    completion_tokens=c_tokens,
                    total_tokens=t_tokens,
                    latency_ms=latency_ms,
                    estimated_cost_usd=cost,
                    model=target_model,
                    provider=self.provider,
                    raw_response=data,
                )

            except Exception as e:
                last_exception = e
                wait_time = 4 * (attempt + 1) if self.provider == "gemini" else 2 * (attempt + 1)
                if attempt < max_retries - 1:
                    logger.warning(f"API call attempt {attempt+1} encountered error ({e}). Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Live API call to {self.provider} failed after {max_retries} attempts: {e}")

        # If live retries were completely exhausted, fall back gracefully rather than crashing with None
        if not self.allow_mock_fallback:
            raise LiveInferenceUnavailable(f"Live call to {self.provider} failed: {last_exception}")
        self.mock_fallbacks += 1
        logger.warning(f"All live API attempts exhausted ({last_exception}). Engaging resilient clinical fallback generator.")
        return self._mock_generate(messages, target_model, failure_reason=str(last_exception or "Rate limit exhausted"))


    # Case-content aware mock profiles. Each key maps recognized clinical
    # keywords to a per-specialty profile so the deterministic mock generator
    # returns plausible, coherent data matching the input case (not just cardiac).
    SPECIALTY_MOCK_PROFILES = {
        "rheumatology": {
            "label": "Acute Gouty Arthritis",
            "reasoning": "Acute monoarticular arthritis with an erythematous, exquisitely tender first MTP joint is the classic gout flare presentation; polarizing microscopy with negative birefringent needle-shaped crystals confirms monosodium urate deposition.",
            "differentials": [
                {"rank": 1, "condition": "Acute Gouty Arthritis", "probability": 0.70, "justification": "Monoarticular podagra with elevated serum urate and characteristic crystals."},
                {"rank": 2, "condition": "Septic Arthritis", "probability": 0.15, "justification": "Acute hot swollen joint must always be aspirated to rule out infection."},
                {"rank": 3, "condition": "Pseudogout (CPPD)", "probability": 0.10, "justification": "Calcium pyrophosphate deposition can mimic the same flare pattern."},
            ],
            "tests": ["Joint aspiration with polarized light microscopy", "Serum uric acid", "Synovial fluid culture & Gram stain"],
            "notes": "All extracted joint findings, serum urate, and crystal analysis accurately reflect the rheumatology vignette.",
            "safety_flags_checked": ["Renal function before NSAID use", "Screen for infection before steroids"],
            "plan": "NSAID or intra-articular corticosteroid (renal impairment: prefer steroids) plus colchicine or IL-1 inhibition as indicated.",
        },
        "neurology": {
            "label": "Acute Peripheral Vestibulopathy / Vestibular Neuritis",
            "reasoning": "Acute-onset rotational vertigo with nausea, without hearing loss or focal neurologic deficits, and a negative HINTS central-sign screen is consistent with vestibular neuritis rather than central posterior-circulation stroke.",
            "differentials": [
                {"rank": 1, "condition": "Vestibular Neuritis (Peripheral Vestibulopathy)", "probability": 0.62, "justification": "Acute vertigo with normal HINTS head-impulse nystagmus skew and no focal signs."},
                {"rank": 2, "condition": "Posterior Circulation Stroke / Cerebellar Infarct", "probability": 0.22, "justification": "Central vertigo must be excluded; subtle ataxia or gaze-holding nystagmus is a red flag."},
                {"rank": 3, "condition": "Benign Paroxysmal Positional Vertigo (BPPV)", "probability": 0.12, "justification": "Positional, brief vertigo on head movement; diagnosed with Dix-Hallpike."},
            ],
            "tests": ["HINTS examination", "Dix-Hallpike positional testing", "MRI/MRA brain if central signs"],
            "notes": "All extracted vestibular symptoms, HINTS findings, and absence of focal deficits accurately reflect the neurology vignette.",
            "safety_flags_checked": ["Rule out central stroke before vestibular suppressants", "Fall risk assessment"],
            "plan": "Vestibular suppressants (meclizine) for symptoms plus vestibular rehabilitation; urgent neuroimaging if any central HINTS finding.",
        },
        "cardiology": {
            "label": "Acute Coronary Syndrome (Non-ST elevation or STEMI)",
            "reasoning": "Exertional retrosternal chest pressure with diaphoresis and cardiovascular risk factors is the archetypal ACS presentation; troponin elevation and ischemic ECG changes support acute myocardial ischemia.",
            "differentials": [
                {"rank": 1, "condition": "Acute Coronary Syndrome", "probability": 0.65, "justification": "Substernal pain, diaphoresis, and cardiovascular risk factors."},
                {"rank": 2, "condition": "Acute Pulmonary Embolism", "probability": 0.20, "justification": "Tachycardia and acute dyspnea without prior warning."},
                {"rank": 3, "condition": "Aortic Dissection", "probability": 0.10, "justification": "Hypertensive patient presenting with severe retrosternal distress."},
            ],
            "tests": ["12-lead ECG", "Serial Troponin-I", "Chest Radiograph", "D-dimer"],
            "notes": "All extracted cardiac biomarkers and vitals accurately reflect the cardiology vignette.",
            "safety_flags_checked": ["Aortic dissection ruled out before heparinization", "Normal renal clearance"],
            "plan": "Aspirin + heparin protocol, serial troponins, urgent cardiology consult.",
        },
        "gastroenterology": {
            "label": "Acute Appendicitis",
            "reasoning": "Periumbilical pain migrating to the right lower quadrant with anorexia, nausea, and localized McBurney tenderness is the classic appendicitis presentation; imaging and lab support confirm the diagnosis.",
            "differentials": [
                {"rank": 1, "condition": "Acute Appendicitis", "probability": 0.70, "justification": "Migratory RLQ pain with McBurney point tenderness and elevated inflammatory markers."},
                {"rank": 2, "condition": "Acute Gastroenteritis", "probability": 0.10, "justification": "Diarrhea and nausea can precede or mimic appendicitis."},
                {"rank": 3, "condition": "Mesenteric Lymphadenitis / Diverticulitis", "probability": 0.10, "justification": "Right-lower-quadrant inflammatory process in the differential."},
            ],
            "tests": ["Abdominal CT with IV contrast", "Complete blood count / CRP", "Right lower quadrant ultrasound"],
            "notes": "All extracted abdominal findings, localized tenderness, and inflammatory markers accurately reflect the GI vignette.",
            "safety_flags_checked": ["Rule out perforation before analgesics/antibiotics", "Fluid resuscitation status"],
            "plan": "Appendectomy consult, IV fluids, empiric broad-spectrum antibiotics (nil-by-mouth).",
        },
        "unmatched": {
            "label": "Demo profile not matched (no diagnosis generated)",
            "reasoning": "The demo generator only recognizes a few specialties by keyword and did not recognize this case. Use a live model for an actual assessment.",
            "differentials": [
                {"rank": 1, "condition": "Demo profile not matched (no diagnosis generated)", "probability": None,
                 "justification": "No keyword profile matched this case."},
            ],
            "tests": ["Run with a live model"],
            "notes": "Demo generator could not interpret this case.",
            "safety_flags_checked": [],
            "plan": "Run with a live model.",
        },
    }

    def _extract_case_text(self, messages: List[Dict[str, str]]) -> str:
        """Return user/task content while excluding role-defining system prompts."""
        case_messages = [
            str(message.get("content", ""))
            for message in messages
            if message.get("role", "").lower() != "system"
        ]
        return " ".join(case_messages or [str(message.get("content", "")) for message in messages])

    def _detect_specialty(self, messages: List[Dict[str, str]]) -> str:
        """Classify clinical case content in the messages into a specialty."""
        case_text = self._extract_case_text(messages).lower()
        if any(k in case_text for k in ("gout", "arthritis", "joint", "urate", "synovial", "podagra",
                                         "birefringent", "crystal", "knee", "effusion")):
            return "rheumatology"
        if any(k in case_text for k in ("vertigo", "dizziness", "vestibular", "nystagmus", "bppv", "labyrinth")):
            return "neurology"
        if any(k in case_text for k in ("abdomen", "appendicitis", "bowel", "colicky", "right lower quadrant", "rlq")) or " gi " in f" {case_text} ":
            return "gastroenterology"
        # Cardiac words are checked last so chest discomfort does not override
        # a stronger specialty-specific presentation.
        if any(k in case_text for k in ("chest", "cardiac", "troponin", "coronary", "ecg", "myocardial", "stem")):
            return "cardiology"
        return "unmatched"

    def _mock_generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        failure_reason: Optional[str] = None,
    ) -> LLMResponse:
        """Deterministic, case-aware, clinically coherent mock generator for local testing & offline development."""
        start_time = time.time()
        time.sleep(0.005)  # simulate processing

        # Identify agent role strictly from system prompt title
        system_msg = (messages[0]["content"] if len(messages) > 1 else "").lower()

        specialty = self._detect_specialty(messages)
        profile = self.SPECIALTY_MOCK_PROFILES[specialty]
        generic_default_note = " [UNMATCHED: no demo profile matched this case]" if specialty == "unmatched" else ""

        if "fact verifier" in system_msg or "grounding auditor" in system_msg:
            content_dict = {
                "verification_status": "VERIFIED_WITH_CAUTIONS",
                "verified_claims_count": 5,
                "unsupported_claims_count": 0,
                "hallucination_detected": False,
                "flagged_claims": [],
                "confidence_score": 0.92,
                "notes": profile["notes"],
            }
        elif "pharmacotherapy validator" in system_msg or "patient protection" in system_msg:
            content_dict = {
                "safety_status": "APPROVED",
                "safety_score": 0.95,
                "contraindications_found": [],
                "critical_red_flags_checked": profile["safety_flags_checked"],
                "safety_flags": [],
                "safe_to_proceed": True,
            }
        elif "gatekeeper" in system_msg or "human-in-the-loop" in system_msg or "attending physician" in system_msg:
            content_dict = {
                "decision": "APPROVED",
                "reviewer_role": f"Attending Physician ({specialty.title()})",
                "clinical_confidence": 0.94,
                "critique": "Diagnostic prioritization and triage pathway are appropriate.",
                "suggested_modifications": None,
                "simulated_physician_minutes": 2.5,
            }
        elif "consistency auditor" in system_msg or "logic & consistency" in system_msg:
            content_dict = {
                "consistency_status": "CONSISTENT",
                "consistency_score": 0.95,
                "inconsistencies_found": [],
                "logical_validity": True,
                "specialty": specialty,
            }
        elif "clinical documentation specialist" in system_msg or "soap" in system_msg:
            content_dict = {
                "report_title": "Structured Clinical Diagnostic Assessment",
                "subjective": f"Patient presenting with acute onset {specialty}-related symptoms requiring differential triage.",
                "objective": "Vitals stable with pertinent specialty-specific findings.",
                "assessment": f"High probability of {profile['label']}; differential and risks under review.",
                "plan": profile["plan"],
                "governance_summary": "Synthesized with active verification and safety assurance.",
            }
        elif "peer reviewer" in system_msg or "quality auditor" in system_msg or "llm judge" in system_msg:
            content_dict = {
                "diagnostic_accuracy": {
                    "score": 0.85,
                    "rationale": f"Primary diagnosis of {profile['label']} is clinically appropriate for the presented {specialty} presentation.",
                },
                "clinical_reasoning_quality": {
                    "score": 0.80,
                    "rationale": "Reasoning follows a structured approach from symptoms to differential.",
                },
                "evidence_grounding": {
                    "score": 0.88,
                    "rationale": "Claims reference specific clinical findings and risk factors from the case.",
                },
                "safety_awareness": {
                    "score": 0.90,
                    "rationale": "Life-threatening differentials appropriately considered.",
                },
                "overall_judge_score": 0.8545,
                "summary": "High-quality clinical output with appropriate differential and safety awareness.",
            }
        elif "chart review" in system_msg or "research" in system_msg:
            content_dict = {
                "patient_summary": f"Patient presenting with acute onset symptoms consistent with {profile['label']}.",
                "chief_complaint": profile["label"],
                "history_present_illness": "Onset over the past several hours with progressive, clinically relevant findings.",
                "pertinent_positives": profile["differentials"][0]["justification"],
                "pertinent_negatives": ["No fever", "No prior related trauma"],
                "risk_factors": ["Relevant past medical history", "Current medication profile"],
            }
        else:  # Diagnosis agent or generic fallback
            content_dict = {
                "primary_diagnosis": profile["label"],
                "reasoning_steps": profile["reasoning"],
                "differential_diagnoses": profile["differentials"],
                "recommended_tests": profile["tests"],
                "case_specialty": specialty,
                "mock_note": "Deterministic case-aware mock output." + generic_default_note,
            }



        content_str = json.dumps(content_dict, indent=2)
        prompt_tokens = len(str(messages)) // 4
        completion_tokens = len(content_str) // 4
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = round((time.time() - start_time) * 1000, 2)
        cost = self.calculate_cost("clinical-mock-v1", prompt_tokens, completion_tokens)

        return LLMResponse(
            content=content_str,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            estimated_cost_usd=cost,
            model="clinical-mock-v1",
            provider="mock" + (f" (fallback from {self.provider}: {failure_reason})" if failure_reason else ""),
            raw_response={"mock": True, "reason": failure_reason},
        )
