"""Base Agent abstract class and utilities."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from src.llm.client import UnifiedLLMClient, LLMResponse
from src.telemetry.metrics import AgentStepLog

PARSE_ERROR = "Failed to parse structured JSON response"


def parse_llm_json(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from LLM output.

    strict=False matters: models routinely emit literal newlines inside string
    values, which strict JSON rejects (29% of stored diagnosis outputs failed on this).
    """
    text = (text or "").strip()
    decoder = json.JSONDecoder(strict=False)
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(text)
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                obj, _ = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return {"raw_text": text, "error": PARSE_ERROR}


def is_parse_failure(output: Any) -> bool:
    return isinstance(output, dict) and output.get("error") == PARSE_ERROR


class BaseClinicalAgent:
    """Base class for all clinical agents and governance modules."""

    def __init__(
        self,
        name: str,
        role: str,
        llm_client: UnifiedLLMClient,
        system_prompt: str,
    ):
        self.name = name
        self.role = role
        self.llm_client = llm_client
        self.system_prompt = system_prompt

    def parse_json_response(self, text: str) -> Dict[str, Any]:
        return parse_llm_json(text)

    def build_step_log(self, response: LLMResponse, output_preview: str, flags: Optional[list] = None) -> AgentStepLog:
        return AgentStepLog(
            agent_name=self.name,
            role=self.role,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            total_tokens=response.total_tokens,
            latency_ms=response.latency_ms,
            cost_usd=response.estimated_cost_usd,
            output_preview=output_preview[:200] + ("..." if len(output_preview) > 200 else ""),
            flags=flags or [],
        )
