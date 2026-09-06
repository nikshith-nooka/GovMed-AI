"""Dataset loader with robust namespace handling, graceful fallbacks, and local caching."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ClinicalDatasetLoader:
    """Loads and formats clinical test cases from HuggingFace and local benchmarks.
    
    Robustness guarantees:
    1. MedQA is prioritized.
    2. MedMCQA uses proper namespace ('openlifescience/medmcqa') and fails gracefully without halting execution.
    3. Always falls back safely to curated benchmark cases if HuggingFace is unreachable.
    """

    CURATED_PATH = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "curated_sample.json"

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/govbench_data")
        os.makedirs(self.cache_dir, exist_ok=True)

    def load_curated_sample(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Loads pre-annotated stratified gold clinical cases."""
        if not self.CURATED_PATH.exists():
            raise FileNotFoundError(f"Curated sample file missing at {self.CURATED_PATH}")

        with open(self.CURATED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if limit:
            return data[:limit]
        return data

    def load_medqa(self, split: str = "test", limit: int = 50) -> List[Dict[str, Any]]:
        """Loads MedQA clinical questions from HuggingFace."""
        try:
            from datasets import load_dataset

            # Try primary bigbio/med_qa or community mirrors
            logger.info("Fetching MedQA cases from HuggingFace...")
            try:
                ds = load_dataset("bigbio/med_qa", "med_qa_en_source", split=split, cache_dir=self.cache_dir)
            except Exception:
                ds = load_dataset("GBaker/MedQA-USMLE-4-options", split=split, cache_dir=self.cache_dir)

            formatted = []
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                raw_opts = row.get("options", {})
                if isinstance(raw_opts, list):
                    options_dict = {
                        item.get("key", chr(65 + idx)): item.get("value", "") if isinstance(item, dict) else str(item)
                        for idx, item in enumerate(raw_opts)
                    }
                elif isinstance(raw_opts, dict):
                    options_dict = raw_opts
                else:
                    options_dict = {}

                ans_idx = row.get("answer_idx", row.get("answer", ""))
                gold_diag = options_dict.get(ans_idx, str(row.get("answer", "")))

                formatted.append({
                    "id": f"medqa_hf_{i+1:03d}",
                    "specialty": row.get("meta_info", "General Medicine"),
                    "difficulty": "USMLE-Standard",
                    "question": row.get("question", ""),
                    "options": options_dict,
                    "answer": ans_idx,
                    "gold_diagnosis": gold_diag,
                })
            logger.info(f"Successfully loaded {len(formatted)} MedQA cases from HuggingFace.")
            return formatted

        except Exception as e:
            logger.warning(f"Could not fetch MedQA from HuggingFace: {e}. Falling back to curated clinical dataset.")
            return self.load_curated_sample(limit)

    def load_medmcqa(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Safely loads MedMCQA with proper repository namespace, skipping gracefully on failure."""
        try:
            from datasets import load_dataset
            # Correct HF namespace for MedMCQA
            logger.info("Attempting to fetch MedMCQA from 'openlifescience/medmcqa'...")
            ds = load_dataset("openlifescience/medmcqa", split="test", cache_dir=self.cache_dir)
            formatted = []
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                formatted.append({
                    "id": f"medmcqa_{i+1:03d}",
                    "specialty": row.get("subject_name", "Medical Exam"),
                    "difficulty": "PG-Level",
                    "question": row.get("question", ""),
                    "options": {
                        "A": row.get("opa", ""),
                        "B": row.get("opb", ""),
                        "C": row.get("opc", ""),
                        "D": row.get("opd", ""),
                    },
                    "answer": ["A", "B", "C", "D"][row.get("cop", 0)],
                    "gold_diagnosis": row.get(f"op{chr(97 + row.get('cop', 0))}", ""),
                })
            return formatted
        except Exception as e:
            logger.warning(
                f"MedMCQA loading skipped gracefully ({e}). Continuing with MedQA and curated benchmark."
            )
            return []

    def load_pubmedqa(self, limit: int = 300) -> List[Dict[str, Any]]:
        """Loads biomedical evidence-grounding cases from qiaojin/PubMedQA."""
        try:
            from datasets import load_dataset
            logger.info("Fetching PubMedQA cases from HuggingFace ('qiaojin/PubMedQA')...")
            ds = load_dataset("qiaojin/PubMedQA", "pqa_labeled", split="train", streaming=True)
            formatted = []
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                # Construct clinical vignette from context and question
                contexts = row.get("context", {}).get("contexts", [])
                context_str = " ".join(contexts[:3]) if isinstance(contexts, list) else str(contexts)
                vignette = f"Clinical Context: {context_str}\n\nClinical Inquiry: {row.get('question', '')}"

                formatted.append({
                    "id": f"pubmedqa_{row.get('pubid', i+1)}",
                    "specialty": "Biomedical Reasoning / Literature Grounding",
                    "difficulty": "Research-Standard",
                    "question": vignette,
                    "options": {"A": "yes", "B": "no", "C": "maybe"},
                    "answer": "A" if row.get("final_decision") == "yes" else ("B" if row.get("final_decision") == "no" else "C"),
                    "gold_diagnosis": f"Conclusion: {row.get('final_decision', '').upper()} - {str(row.get('long_answer', ''))[:120]}",
                    "source_dataset": "PubMedQA",
                })
            logger.info(f"Successfully loaded {len(formatted)} PubMedQA cases.")
            return formatted
        except Exception as e:
            logger.warning(f"PubMedQA loading skipped gracefully ({e}).")
            return []

    def load_meddialog(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Loads doctor-patient interactive dialogue consultations from open HuggingFace corpus."""
        try:
            from datasets import load_dataset
            logger.info("Fetching Clinical Dialogue cases from 'lavita/ChatDoctor-HealthCareMagic-100k'...")
            ds = load_dataset("lavita/ChatDoctor-HealthCareMagic-100k", split="train", streaming=True)
            formatted = []
            for i, row in enumerate(ds):
                if i >= limit:
                    break
                patient_input = row.get("input", "") or row.get("instruction", "")
                doctor_output = row.get("output", "")

                formatted.append({
                    "id": f"meddialog_{i+1:03d}",
                    "specialty": "Doctor-Patient Clinical Dialogue",
                    "difficulty": "Conversational / Incomplete",
                    "question": f"Patient Consultation Transcript:\n{patient_input}",
                    "options": {},
                    "answer": "N/A",
                    "gold_diagnosis": f"Attending Physician Advice: {doctor_output[:150]}...",
                    "source_dataset": "MedDialog",
                })
            logger.info(f"Successfully loaded {len(formatted)} MedDialog cases.")
            return formatted
        except Exception as e:
            logger.warning(f"MedDialog loading skipped gracefully ({e}).")
            return []

    def load_stratified_benchmark(
        self,
        target_count: int = 2000,
        medqa_ratio: float = 0.50,
        medmcqa_ratio: float = 0.25,
        pubmedqa_ratio: float = 0.15,
        meddialog_ratio: float = 0.10,
    ) -> List[Dict[str, Any]]:
        """Loads a stratified benchmark population matching the paper's target composition.
        
        Target Distribution (for 2,000 cases):
        - MedQA-USMLE: 1,000 cases (50%)
        - MedMCQA: 500 cases (25%)
        - PubMedQA: 300 cases (15%)
        - MedDialog: 200 cases (10%)
        """
        n_medqa = int(target_count * medqa_ratio)
        n_medmcqa = int(target_count * medmcqa_ratio)
        n_pubmedqa = int(target_count * pubmedqa_ratio)
        n_meddialog = target_count - (n_medqa + n_medmcqa + n_pubmedqa)

        logger.info(f"Assembling stratified benchmark: {n_medqa} MedQA, {n_medmcqa} MedMCQA, {n_pubmedqa} PubMedQA, {n_meddialog} MedDialog")

        cases: List[Dict[str, Any]] = []
        cases.extend(self.load_medqa(limit=n_medqa))
        cases.extend(self.load_medmcqa(limit=n_medmcqa))
        cases.extend(self.load_pubmedqa(limit=n_pubmedqa))
        cases.extend(self.load_meddialog(limit=n_meddialog))

        # If any remote sets could not reach target, fill with curated sample
        if len(cases) < target_count:
            curated = self.load_curated_sample()
            deficit = target_count - len(cases)
            for i in range(deficit):
                sample = curated[i % len(curated)].copy()
                sample["id"] = f"{sample['id']}_fill_{i+1}"
                cases.append(sample)

        logger.info(f"Stratified benchmark population assembled: {len(cases)} total cases.")
        return cases[:target_count]

    def load_equal_per_db(self, per_db_count: int = 1000) -> List[Dict[str, Any]]:
        """Loads an equal number (e.g. 1,000) of cases from each clinical database.
        
        - 1,000 from MedQA-USMLE (Diagnostic Board Reasoning)
        - 1,000 from PubMedQA (Biomedical Evidence Grounding)
        - 1,000 from MedDialog (Doctor-Patient Consultations)
        Total: 3,000 cases across 3 foundational medical databases.
        """
        logger.info(f"Assembling equal benchmark: {per_db_count} from MedQA, {per_db_count} from PubMedQA, {per_db_count} from MedDialog...")
        medqa_cases = self.load_medqa(limit=per_db_count)
        logger.info(f"Loaded {len(medqa_cases)} cases from MedQA.")

        pqa_cases = self.load_pubmedqa(limit=per_db_count)
        logger.info(f"Loaded {len(pqa_cases)} cases from PubMedQA.")

        md_cases = self.load_meddialog(limit=per_db_count)
        logger.info(f"Loaded {len(md_cases)} cases from MedDialog.")

        # Interleave round-robin so all datasets make balanced, simultaneous progress in benchmarks
        cases: List[Dict[str, Any]] = []
        max_len = max(len(medqa_cases), len(pqa_cases), len(md_cases))
        for i in range(max_len):
            if i < len(medqa_cases):
                cases.append(medqa_cases[i])
            if i < len(pqa_cases):
                cases.append(pqa_cases[i])
            if i < len(md_cases):
                cases.append(md_cases[i])

        logger.info(f"Total equal-split dataset assembled: {len(cases)} cases interleaved across all medical DBs.")
        return cases

    def get_benchmark_cases(self, requested_count: int = 10, source: str = "curated") -> List[Dict[str, Any]]:
        """Unified access point returning requested number of stratified cases."""
        source = source.lower()
        if source == "curated":
            cases = self.load_curated_sample(requested_count)
            if len(cases) < requested_count:
                expanded = []
                for i in range(requested_count):
                    base = cases[i % len(cases)].copy()
                    base["id"] = f"{base['id']}_run{i+1}"
                    expanded.append(base)
                return expanded
            return cases

        elif source in ("equal_50", "balanced_50", "50_each"):
            return self.load_equal_per_db(per_db_count=50)

        elif source in ("equal_1000", "balanced_1000", "all_dbs_1000"):
            return self.load_equal_per_db(per_db_count=1000)


        elif source == "pubmedqa":
            return self.load_pubmedqa(limit=requested_count)

        elif source == "meddialog":
            return self.load_meddialog(limit=requested_count)

        elif source in ("stratified", "stratified_2000", "all"):
            return self.load_stratified_benchmark(target_count=requested_count)

        # Default fallback: MedQA
        hf_cases = self.load_medqa(limit=requested_count)
        if len(hf_cases) >= requested_count:
            return hf_cases[:requested_count]

        curated = self.load_curated_sample()
        combined = hf_cases + curated
        return combined[:requested_count]


