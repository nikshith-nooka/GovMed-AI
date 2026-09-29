"""Detects direct patient identifiers in free text before it is sent to an external model.

Reports identifier TYPES and counts only; matched values are never returned or logged. The
patterns favour recall on the HIPAA Safe Harbor identifiers most often pasted into a case box
(names with titles, record numbers, SSN, phone, email, dates, street addresses, Aadhaar).
A clean result is not a de-identification guarantee.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

PHI_PATTERNS: Dict[str, List[re.Pattern]] = {
    "name_with_title": [
        re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof)\.?\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?\b"),
        re.compile(r"\b(?:patient(?:'s)? name|name|pt name)\s*[:=]\s*[A-Z][a-z]+", re.I),
    ],
    "medical_record_number": [
        re.compile(r"\b(?:MRN|medical record(?: number| no\.?| #)?|hospital (?:number|no\.?)|patient id|UHID|IP no\.?)"
                   r"\s*[:#]?\s*[A-Z]{0,3}[-\s]?\d[\dA-Z-]{3,}", re.I),
    ],
    "ssn": [re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")],
    "phone": [
        re.compile(r"(?<![\d/.-])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\d/-])"),
        re.compile(r"(?<!\d)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"),
        re.compile(r"\b(?:phone|tel|mobile|cell|contact)\s*(?:no\.?|number|#)?\s*[:#]?\s*\+?\d[\d\s().-]{7,}\d", re.I),
    ],
    "email": [re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")],
    "date_of_birth": [
        re.compile(r"\b(?:DOB|D\.O\.B\.?|date of birth|birth ?date|born(?: on)?)\s*[:\-]?\s*"
                   r"(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4}|\d{1,2} [A-Z][a-z]{2,8}\.? \d{4})",
                   re.I),
    ],
    "full_date": [
        re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)\d{2}\b"),
        re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b"),
        re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2},? (?:19|20)\d{2}\b"),
    ],
    "street_address": [
        re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|"
                   r"Court|Ct|Way|Place|Pl|Terrace|Highway|Hwy|Nagar|Marg|Colony)\b\.?"),
    ],
    "aadhaar": [re.compile(r"(?<!\d)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")],
}

LABELS = {
    "name_with_title": "patient or clinician name with a title (e.g. Mr./Dr. Surname)",
    "medical_record_number": "medical record / hospital number",
    "ssn": "US Social Security number",
    "phone": "phone number",
    "email": "email address",
    "date_of_birth": "date of birth",
    "full_date": "full calendar date (day, month and year)",
    "street_address": "street address",
    "aadhaar": "Aadhaar-like 12-digit number",
}


def detect_phi(texts: Iterable[str]) -> List[Dict[str, object]]:
    """[{type, label, count}] for each identifier type found; never the matched text."""
    blob = "\n".join(t for t in texts if t)
    found: Dict[str, int] = {}
    date_of_birth_spans = [m.span() for p in PHI_PATTERNS["date_of_birth"] for m in p.finditer(blob)]
    for kind, patterns in PHI_PATTERNS.items():
        spans = {m.span() for p in patterns for m in p.finditer(blob)}
        if kind == "full_date":  # a DOB is already reported as such
            spans = {s for s in spans if not any(a <= s[0] and s[1] <= b for a, b in date_of_birth_spans)}
        # Overlapping matches from different patterns are one identifier.
        merged: List[List[int]] = []
        for a, b in sorted(spans):
            if merged and a < merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        if merged:
            found[kind] = len(merged)
    return [{"type": kind, "label": LABELS[kind], "count": count} for kind, count in found.items()]
