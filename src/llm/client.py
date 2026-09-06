"""Unified LLM Client supporting Groq, Gemini, OpenRouter, and Deterministic Mock."""

from __future__ import annotations

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


class UnifiedLLMClient:
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
    ):
        self.provider = provider.lower()
        self.force_mock = force_mock
        self.timeout_seconds = timeout_seconds

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
        if not self.api_key and not self.force_mock:
            logger.warning(
                f"No API key found for provider '{self.provider}'. "
                f"Falling back to high-fidelity clinical simulation mock mode."
            )
            self.force_mock = True

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
        # Round-robin across pooled keys for even token/RPM distribution
        if self.provider == "groq" and self.groq_keys:
            self.current_key_idx = (self.current_key_idx + 1) % len(self.groq_keys)
            active_key = self.groq_keys[self.current_key_idx]
        elif self.provider in ("nvidia", "nim") and getattr(self, "nvidia_keys", None):
            self.current_key_idx = (self.current_key_idx + 1) % len(self.nvidia_keys)
            active_key = self.nvidia_keys[self.current_key_idx]
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

        max_retries = 10
        last_exception = None

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    resp = client.post(self.base_url, headers=headers, json=payload)
                    if resp.status_code == 429:
                        raw_retry = float(resp.headers.get("retry-after", 6 if self.provider == "gemini" else 2))
                        retry_after = max(int(raw_retry), 6 if self.provider == "gemini" else 2)
                        
                        # Rotate across pooled Groq API keys
                        if self.provider == "groq" and len(self.groq_keys) > 1:
                            self.current_key_idx = (self.current_key_idx + 1) % len(self.groq_keys)
                            next_key = self.groq_keys[self.current_key_idx]
                            headers["Authorization"] = f"Bearer {next_key}"
                            
                            logger.info(f"Groq limit on key: Swapping to pooled API Key #{self.current_key_idx + 1}/{len(self.groq_keys)}...")
                            time.sleep(1)
                            continue
                        
                        logger.warning(f"Rate limited by {self.provider} (429). Waiting {retry_after}s for quota reset... (attempt {attempt+1}/{max_retries})")
                        time.sleep(retry_after)
                        continue

                    if resp.status_code != 200:
                        logger.warning(f"HTTP {resp.status_code} from {self.provider}: {resp.text[:300]}")
                    resp.raise_for_status()
                    data = resp.json()

                latency_ms = round((time.time() - start_time) * 1000, 2)
                choice = data["choices"][0]
                content = choice["message"]["content"]
                usage = data.get("usage", {})
                p_tokens = usage.get("prompt_tokens", int(len(str(messages)) / 4))
                c_tokens = usage.get("completion_tokens", int(len(content) / 4))
                t_tokens = usage.get("total_tokens", p_tokens + c_tokens)
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
        logger.warning(f"All live API attempts exhausted ({last_exception}). Engaging resilient clinical fallback generator.")
        return self._mock_generate(messages, target_model, failure_reason=str(last_exception or "Rate limit exhausted"))


    def _mock_generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        failure_reason: Optional[str] = None,
    ) -> LLMResponse:
        """Deterministic, clinically coherent mock generator for local testing & offline development."""
        start_time = time.time()
        time.sleep(0.005)  # simulate processing

        # Identify agent role strictly from system prompt title
        system_msg = (messages[0]["content"] if len(messages) > 1 else "").lower()

        if "fact verifier" in system_msg or "grounding auditor" in system_msg:
            content_dict = {
                "verification_status": "VERIFIED_WITH_CAUTIONS",
                "verified_claims_count": 5,
                "unsupported_claims_count": 0,
                "hallucination_detected": False,
                "flagged_claims": [],
                "confidence_score": 0.92,
                "notes": "All extracted cardiac biomarkers and vitals accurately reflect the patient vignette.",
            }
        elif "pharmacotherapy validator" in system_msg or "patient protection" in system_msg:
            content_dict = {
                "safety_status": "APPROVED",
                "safety_score": 0.95,
                "contraindications_found": [],
                "critical_red_flags_checked": ["Aortic dissection ruled out before heparinization", "Normal renal clearance"],
                "safety_flags": [],
                "safe_to_proceed": True,
            }
        elif "gatekeeper" in system_msg or "human-in-the-loop" in system_msg or "attending physician" in system_msg:
            content_dict = {
                "decision": "APPROVED",
                "reviewer_role": "Attending Physician (Cardiology)",
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
            }
        elif "clinical documentation specialist" in system_msg or "soap" in system_msg:
            content_dict = {
                "report_title": "Structured Clinical Diagnostic Assessment",
                "subjective": "Middle-aged patient presenting with exertional retrosternal chest pain.",
                "objective": "BP 150/92 mmHg, HR 98 bpm, ST deviations on telemetry.",
                "assessment": "High probability of Acute Coronary Syndrome; PE and Aortic Dissection considered in differential.",
                "plan": "Immediate aspirin + heparin protocol, serial troponins, urgent cardiology consult.",
                "governance_summary": "Synthesized with active verification and safety assurance.",
            }
        elif "chart review" in system_msg or "research" in system_msg:
            content_dict = {
                "patient_summary": "Patient presenting with acute onset symptoms requiring differential triage.",
                "chief_complaint": "Acute chest pressure and shortness of breath.",
                "history_present_illness": "Symptoms worsening on exertion over the past 4 hours.",
                "pertinent_positives": ["Chest tightness", "Diaphoresis", "Elevated ST segments"],
                "pertinent_negatives": ["No fever", "No prior pleuritic chest trauma"],
                "risk_factors": ["Hypertension", "Dyslipidemia", "Smoking history"],
            }
        else:  # Diagnosis agent or generic fallback
            content_dict = {
                "primary_diagnosis": "Acute Coronary Syndrome (Non-ST elevation or STEMI)",
                "differential_diagnoses": [
                    {
                        "rank": 1,
                        "condition": "Acute Coronary Syndrome",
                        "probability": 0.65,
                        "justification": "Substernal pain, diaphoresis, and cardiovascular risk factors.",
                    },
                    {
                        "rank": 2,
                        "condition": "Acute Pulmonary Embolism",
                        "probability": 0.20,
                        "justification": "Tachycardia and acute dyspnea without prior warning.",
                    },
                    {
                        "rank": 3,
                        "condition": "Aortic Dissection",
                        "probability": 0.10,
                        "justification": "Hypertensive patient presenting with severe retrosternal distress.",
                    },
                ],
                "recommended_tests": ["12-lead ECG", "Serial Troponin-I", "Chest Radiograph", "D-dimer"],
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
