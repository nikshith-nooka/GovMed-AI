"""Base Agent abstract class and utilities."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from src.llm.client import UnifiedLLMClient, LLMResponse
from src.telemetry.metrics import AgentStepLog


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
        """Safely parses JSON from LLM text output, handling markdown blocks."""
        text = text.strip()
        # Remove ```json ... ``` wrappers
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                text = match.group(1)
            else:
                match2 = re.search(r"(\{.*\})", text, re.DOTALL)
                if match2:
                    text = match2.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Simple heuristic salvage
            return {
                "raw_text": text,
                "error": "Failed to parse structured JSON response",
            }

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
