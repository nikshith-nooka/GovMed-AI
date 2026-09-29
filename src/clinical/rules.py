"""Deterministic contraindication rules that run independently of the LLM.

The model-based safety validator can miss a hazard, be talked out of one, or not run at all
(G0/G1). These rules read the structured case fields, the free text, and the drugs the AI
proposes, and fire on well-established drug-condition and drug-drug hazards. They are a
floor, not a formulary: a rule that does not fire is not evidence that a plan is safe.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------- vocabularies
NSAIDS = ("indomethacin", "ibuprofen", "naproxen", "diclofenac", "ketorolac", "meloxicam", "celecoxib",
          "etoricoxib", "piroxicam", "ketoprofen", "nsaid", "nsaids")
ANTICOAGULANTS = ("warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban", "enoxaparin", "heparin",
                  "coumadin", "eliquis", "xarelto")
ACE_ARB = ("lisinopril", "enalapril", "ramipril", "captopril", "perindopril", "benazepril", "quinapril",
           "losartan", "valsartan", "irbesartan", "candesartan", "telmisartan", "olmesartan",
           "ace inhibitor", "ace-inhibitor", "acei", "arb")
BETA_BLOCKERS = ("propranolol", "metoprolol", "atenolol", "carvedilol", "labetalol", "bisoprolol", "esmolol",
                 "nadolol", "sotalol", "timolol", "beta-blocker", "beta blocker")
THROMBOLYTICS = ("alteplase", "tenecteplase", "reteplase", "streptokinase", "tpa", "rtpa", "thrombolysis",
                 "thrombolytic", "thrombolytics", "fibrinolytic", "fibrinolysis")
PENICILLINS = ("penicillin", "amoxicillin", "ampicillin", "piperacillin", "nafcillin", "oxacillin",
               "dicloxacillin", "flucloxacillin", "augmentin", "amoxicillin-clavulanate", "co-amoxiclav",
               "zosyn", "piperacillin-tazobactam", "benzylpenicillin")
CEPHALOSPORINS = ("cephalexin", "cefazolin", "cefuroxime", "ceftriaxone", "cefotaxime", "cefepime", "ceftazidime")
QT_ANTIBIOTICS = ("azithromycin", "clarithromycin", "erythromycin", "levofloxacin", "ciprofloxacin",
                  "moxifloxacin", "ofloxacin")
QT_DRUGS = ("amiodarone", "sotalol", "dofetilide", "haloperidol", "ondansetron", "methadone", "citalopram",
            "escitalopram", "quetiapine", "hydroxychloroquine", "domperidone", "droperidol")
AMINOGLYCOSIDES = ("gentamicin", "tobramycin", "amikacin", "streptomycin")
TRIMETHOPRIM = ("trimethoprim", "co-trimoxazole", "cotrimoxazole", "bactrim", "tmp-smx", "sulfamethoxazole")
PDE5 = ("sildenafil", "tadalafil", "vardenafil", "avanafil", "viagra", "cialis")
NITRATES = ("nitroglycerin", "nitroglycerine", "glyceryl trinitrate", "gtn", "isosorbide mononitrate",
            "isosorbide dinitrate", "isosorbide", "nitrate", "nitrates")
TRIPTANS = ("sumatriptan", "rizatriptan", "zolmitriptan", "eletriptan", "naratriptan", "almotriptan",
            "frovatriptan", "triptan")

# A cue negates a term only within the same clause (text after the last comma / "but").
NEGATION_RE = re.compile(r"\b(no|not|denies|denied|without|negative for|avoid|avoiding|hold|held|stop|stopped|"
                         r"discontinue|discontinued|contraindicated|instead of|rather than|never|free of|ruled out)\b", re.I)
ALLERGY_CUE = re.compile(r"allerg|anaphyla|hypersensitivity|intoleran", re.I)
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _term_re(terms: Iterable[str]) -> re.Pattern:
    alternatives = sorted({re.escape(t) for t in terms}, key=len, reverse=True)
    return re.compile(r"(?<![a-z])(" + "|".join(alternatives) + r")(?![a-z])", re.I)


def _segments(text: str) -> List[str]:
    """Clauses short enough that a negation cue refers to the nearby term."""
    return [s for s in re.split(r"[\n;]|(?<=[.!?])\s+", text or "") if s.strip()]


def _negated(segment: str, start: int) -> bool:
    window = re.split(r",|\bbut\b|\bhowever\b", segment[max(0, start - 45):start], flags=re.I)[-1]
    return bool(NEGATION_RE.search(window))


def _mentions(regex: str, text: str) -> bool:
    """A non-negated match of a condition regex anywhere in the text."""
    return any(not _negated(seg, m.start()) for seg in _segments(text) for m in re.finditer(regex, seg, re.I))


def _find(terms: Iterable[str], text: str) -> List[str]:
    """Non-negated mentions of any term, lower-cased and de-duplicated in order of appearance."""
    pattern, found = _term_re(terms), []
    for segment in _segments(text):
        for match in pattern.finditer(segment):
            term = match.group(1).lower()
            if not _negated(segment, match.start()) and term not in found:
                found.append(term)
    return found


def _number_after(label: str, text: str, max_gap: int = 18) -> Optional[float]:
    match = re.search(label + r"[^0-9\n]{0,%d}?(\d+(?:\.\d+)?)" % max_gap, text or "", re.I)
    return float(match.group(1)) if match else None


# ---------------------------------------------------------------- case facts
@dataclass
class CaseFacts:
    drugs_text: str          # current meds, drugs under consideration, and the AI plan (allergy clauses removed)
    condition_text: str      # history, presentation, labs (allergy clauses removed)
    allergy_text: str
    plan_text: str
    egfr: Optional[float]
    creatinine_mg_dl: Optional[float]
    potassium: Optional[float]


CLAUSE_SPLIT = re.compile(r",|\bbut\b|\bhowever\b|\bwhile\b|\bwhereas\b|\band\b(?=\s+(?:currently|now|on|taking|started)\b)", re.I)
ACTIVE_USE = re.compile(r"\b(?:prescrib\w*|start\w*|taking|takes|on|given|receiv\w*|currently|now|plan\w*|consider\w*|"
                        r"administer\w*|dose\w*|daily|bid|tid|qid|\d+\s*mg)\b", re.I)


def _split_allergy(text: str) -> Tuple[str, str]:
    """Separate allergy statements from the rest, clause by clause.

    Notes often put an allergy and an active drug in one sentence ("Allergic to penicillin, currently prescribed
    amoxicillin"), so a sentence with an allergy cue is split at commas and contrast words. A clause right after an
    allergy clause stays part of the allergy list ("allergic to penicillin, sulfa") unless it describes active use.
    """
    kept, allergy = [], []
    for segment in _segments(text):
        if not ALLERGY_CUE.search(segment):
            kept.append(segment)
            continue
        in_allergy = False
        for clause in (c for c in CLAUSE_SPLIT.split(segment) if c and c.strip()):
            if ALLERGY_CUE.search(clause):
                allergy.append(clause)
                in_allergy = True
            elif in_allergy and not ACTIVE_USE.search(clause):
                allergy.append(clause)
            else:
                kept.append(clause)
                in_allergy = False
    return "\n".join(kept), "\n".join(allergy)


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return "\n".join(_flatten(v) for v in value)
    return str(value)


def _egfr(text: str) -> Optional[float]:
    value = _number_after(r"\be?gfr\b", text) or _number_after(r"\bcr?cl\b|creatinine clearance", text)
    if value is not None:
        return value
    stage = re.search(r"\b(?:ckd|chronic kidney disease)[^0-9\n]{0,12}(?:stage\s*)?([1-5])\s*([ab])?", text, re.I)
    if stage:  # upper bound of the KDIGO G-category
        return {"1": 90, "2": 89, "3": 59, "4": 29, "5": 14}[stage.group(1)] if not stage.group(2) else \
            {"a": 59, "b": 44}[stage.group(2).lower()]
    return None


def _creatinine(text: str) -> Optional[float]:
    match = re.search(r"\b(?:serum\s+)?(?:creatinine|creat|scr|cr)\b[^0-9\n]{0,12}?(\d+(?:\.\d+)?)\s*(mg/dl|µmol/l|umol/l|micromol/l)?",
                      text or "", re.I)
    if not match:
        return None
    value, unit = float(match.group(1)), (match.group(2) or "").lower()
    return round(value / 88.4, 2) if ("mol" in unit or value > 20) else value


def extract_facts(clinical_case: Dict[str, Any], diagnosis: Optional[Dict[str, Any]] = None) -> CaseFacts:
    fields = clinical_case.get("structured") or {}
    free_text = str(clinical_case.get("question") or clinical_case.get("clinical_note") or "")
    diagnosis = diagnosis if isinstance(diagnosis, dict) else {}
    plan_text = _flatten([diagnosis.get(k) for k in ("recommended_next_steps", "recommended_tests", "plan",
                                                     "treatment_plan", "primary_justification")])
    body, allergy_in_text = _split_allergy("\n".join([free_text, _flatten(fields.get("medications")),
                                                      _flatten(fields.get("pmh"))]))
    plan_body, _ = _split_allergy(plan_text)
    labs = "\n".join([_flatten(fields.get("labs")), body])
    return CaseFacts(
        drugs_text="\n".join([body, plan_body]),
        condition_text="\n".join([body, _flatten(fields.get("labs")), _flatten(fields.get("vitals"))]),
        allergy_text="\n".join([_flatten(fields.get("allergies")), allergy_in_text]),
        plan_text=plan_body,
        egfr=_egfr(labs),
        creatinine_mg_dl=_creatinine(labs),
        potassium=_number_after(r"\b(?:potassium|k\+?)(?=[\s:=])", labs, max_gap=8),
    )


def renal_impairment(f: CaseFacts) -> Optional[str]:
    if f.egfr is not None and f.egfr < 60:
        return f"eGFR {f.egfr:g} mL/min"
    if f.creatinine_mg_dl is not None and f.creatinine_mg_dl > 1.3:
        return f"creatinine {f.creatinine_mg_dl:g} mg/dL"
    if _mentions(r"\b(ckd|chronic kidney disease|renal (insufficiency|impairment|failure)|esrd|dialysis|aki|acute kidney injury)\b",
            f.condition_text):
        return "documented kidney disease"
    return None


def penicillin_allergy(f: CaseFacts) -> bool:
    return bool(_find(PENICILLINS + ("beta-lactam", "beta lactam"), f.allergy_text))


# ---------------------------------------------------------------- rules
@dataclass
class Rule:
    rule_id: str
    title: str
    check: Callable[[CaseFacts], Optional[Tuple[str, str, str]]]  # -> (severity, description, action) or None
    reference: str


def _drugs(f: CaseFacts, terms: Iterable[str]) -> List[str]:
    return _find(terms, f.drugs_text)


def _nsaid_renal(f: CaseFacts):
    drugs, renal = _drugs(f, NSAIDS), renal_impairment(f)
    if drugs and renal:
        severe = f.egfr is not None and f.egfr < 30
        return ("CRITICAL" if severe else "HIGH",
                f"{', '.join(drugs)} with renal impairment ({renal}). NSAIDs reduce renal perfusion and can "
                "precipitate acute kidney injury and hyperkalemia.",
                "Avoid NSAIDs; consider alternatives (e.g. for gout: colchicine at renally adjusted dose, or "
                "oral/intra-articular corticosteroid).")
    return None


def _nsaid_anticoag(f: CaseFacts):
    drugs, anticoag = _drugs(f, NSAIDS), _drugs(f, ANTICOAGULANTS)
    if drugs and anticoag:
        return ("HIGH", f"{', '.join(drugs)} with anticoagulant ({', '.join(anticoag)}): additive bleeding risk; "
                "warfarin + NSAID also raises INR and GI bleeding risk.",
                "Avoid the NSAID; use paracetamol/acetaminophen or a non-NSAID alternative; if unavoidable, add GI protection and monitor.")
    return None


def _nsaid_ulcer(f: CaseFacts):
    drugs = _drugs(f, NSAIDS)
    if drugs and _mentions(r"\b(peptic ulcer|pud|gastric ulcer|duodenal ulcer|gi bleed|gastrointestinal bleed|upper gi bleed|melaena|melena|hematemesis|haematemesis)\b",
                      f.condition_text):
        return ("HIGH", f"{', '.join(drugs)} with peptic ulcer disease or GI bleeding history.",
                "Avoid NSAIDs; if essential use the lowest dose with a proton-pump inhibitor.")
    return None


def _metformin_renal(f: CaseFacts):
    if not _drugs(f, ("metformin",)) or f.egfr is None:
        return None
    if f.egfr < 30:
        return ("HIGH", f"Metformin with eGFR {f.egfr:g} mL/min (contraindicated below 30): risk of lactic acidosis.",
                "Stop or do not start metformin; choose an agent suitable for severe CKD.")
    if f.egfr < 45:
        return ("MEDIUM", f"Metformin with eGFR {f.egfr:g} mL/min: initiation not recommended between 30 and 45.",
                "Do not initiate; if already taking, reassess benefit and reduce dose.")
    return None


def _acei_hyperk(f: CaseFacts):
    drugs = _drugs(f, ACE_ARB)
    high_k = (f.potassium is not None and f.potassium >= 5.5) or _mentions(r"\bhyperkal(a)?emia\b", f.condition_text)
    if drugs and high_k:
        level = f"K {f.potassium:g} mmol/L" if f.potassium is not None else "documented hyperkalemia"
        return ("HIGH", f"{', '.join(drugs)} with hyperkalemia ({level}): ACE inhibitors/ARBs raise potassium further.",
                "Hold the ACE inhibitor/ARB and treat hyperkalemia; recheck potassium and renal function.")
    return None


def _acei_pregnancy(f: CaseFacts):
    drugs = _drugs(f, ACE_ARB)
    if drugs and _mentions(r"\b(pregnan(t|cy)|gestation(al)?|trimester|weeks pregnant|g\d+p\d+)\b", f.condition_text):
        return ("CRITICAL", f"{', '.join(drugs)} in pregnancy: boxed warning for fetal renal toxicity and death.",
                "Stop immediately; use a pregnancy-compatible antihypertensive (e.g. labetalol, nifedipine, methyldopa).")
    return None


def _bb_asthma(f: CaseFacts):
    drugs = _drugs(f, BETA_BLOCKERS)
    acute = _mentions(r"\b(asthma (exacerbation|attack)|acute asthma|status asthmaticus|bronchospasm)\b", f.condition_text) or (
        _mentions(r"\basthma\b", f.condition_text) and _mentions(r"\bwheez", f.condition_text))
    if drugs and acute:
        return ("HIGH", f"{', '.join(drugs)} during acute asthma/bronchospasm: beta-blockade can cause severe bronchospasm.",
                "Avoid beta-blockers in acute asthma; if rate control is essential, consider a non-beta-blocker option.")
    return None


def _thrombolysis_bleed(f: CaseFacts):
    drugs = _drugs(f, THROMBOLYTICS)
    risk = _mentions(r"\b(intracranial (hemorrhage|haemorrhage|bleed)|hemorrhagic stroke|haemorrhagic stroke|active (bleeding|hemorrhage)|"
                r"subarachnoid|(recent|prior|previous) (stroke|bleed(ing)?|hemorrhage|haemorrhage|surgery|head trauma)|"
                r"gi bleed|aortic dissection)\b", f.condition_text)
    if drugs and risk:
        return ("CRITICAL", f"{', '.join(drugs)} with recent/active bleeding, prior intracranial hemorrhage, recent stroke or surgery.",
                "Do not give thrombolysis until contraindications are excluded; seek specialist input (e.g. mechanical thrombectomy / PCI).")
    return None


def _penicillin_allergy(f: CaseFacts):
    if not penicillin_allergy(f):
        return None
    drugs = _drugs(f, PENICILLINS)
    if drugs:
        return ("HIGH", f"{', '.join(drugs)} prescribed/considered with a documented penicillin allergy.",
                "Choose a non-beta-lactam alternative or clarify the allergy history before giving.")
    cephs = _drugs(f, CEPHALOSPORINS)
    if cephs:
        return ("MEDIUM", f"{', '.join(cephs)} with a documented penicillin allergy: low but real cross-reactivity.",
                "Clarify the reaction type; avoid if the allergy was anaphylactic.")
    return None


def _qt(f: CaseFacts):
    abx, other = _drugs(f, QT_ANTIBIOTICS), _drugs(f, QT_DRUGS)
    long_qt = _mentions(r"\b(long qt|qt prolongation|prolonged qtc?|qtc (of )?(4[7-9]\d|[5-9]\d\d))\b", f.condition_text)
    if abx and (other or long_qt):
        partner = ", ".join(other) if other else "a prolonged QT interval"
        return ("HIGH", f"{', '.join(abx)} with {partner}: additive QT prolongation and torsades risk.",
                "Choose a non-QT-prolonging antibiotic or check the ECG/electrolytes and monitor.")
    return None


def _aminoglycoside_renal(f: CaseFacts):
    drugs, renal = _drugs(f, AMINOGLYCOSIDES), renal_impairment(f)
    if drugs and renal:
        return ("HIGH", f"{', '.join(drugs)} with renal impairment ({renal}): nephrotoxicity and ototoxicity risk.",
                "Avoid or dose by levels with renal adjustment; prefer a non-nephrotoxic alternative.")
    return None


def _mtx_tmp(f: CaseFacts):
    if _drugs(f, ("methotrexate",)) and _drugs(f, TRIMETHOPRIM):
        return ("HIGH", "Methotrexate with trimethoprim/co-trimoxazole: additive antifolate effect and reduced "
                "clearance can cause fatal pancytopenia.",
                "Avoid the combination; choose a different antibiotic.")
    return None


def _pde5_nitrate(f: CaseFacts):
    pde5, nitrates = _drugs(f, PDE5), _drugs(f, NITRATES)
    if pde5 and nitrates:
        return ("CRITICAL", f"{', '.join(pde5)} with nitrate ({', '.join(nitrates)}): profound, potentially fatal hypotension.",
                "Do not give nitrates within 24 h of sildenafil/vardenafil (48 h of tadalafil); use alternatives.")
    return None


def _triptan_cad(f: CaseFacts):
    drugs = _drugs(f, TRIPTANS)
    cad = _mentions(r"\b(coronary artery disease|cad|ischemic heart disease|ischaemic heart disease|prior mi|previous mi|"
               r"myocardial infarction|angina|coronary stent|cabg|prinzmetal)\b", f.condition_text)
    if drugs and cad:
        return ("HIGH", f"{', '.join(drugs)} with coronary artery disease: triptans cause coronary vasoconstriction.",
                "Avoid triptans; use a non-vasoconstrictive migraine treatment.")
    return None


RULES: List[Rule] = [
    Rule("nsaid_renal", "NSAID with renal impairment", _nsaid_renal,
         "KDIGO 2012 CKD guideline (avoid NSAIDs with GFR <30, caution <60); AGS Beers Criteria 2023"),
    Rule("nsaid_anticoagulant", "NSAID with anticoagulant (incl. warfarin + NSAID)", _nsaid_anticoag,
         "Warfarin and DOAC drug labels (bleeding interactions); AGS Beers Criteria 2023"),
    Rule("nsaid_ulcer", "NSAID with peptic ulcer / GI bleed", _nsaid_ulcer,
         "NSAID class drug label boxed warning (GI bleeding); ACG peptic ulcer guideline"),
    Rule("metformin_renal", "Metformin with low eGFR", _metformin_renal,
         "FDA metformin labeling (2016): contraindicated eGFR <30, do not initiate 30-45"),
    Rule("acei_arb_hyperkalemia", "ACE inhibitor/ARB with hyperkalemia", _acei_hyperk,
         "ACE inhibitor/ARB drug labels; KDIGO 2020 guidance on RAAS blockade"),
    Rule("acei_arb_pregnancy", "ACE inhibitor/ARB in pregnancy", _acei_pregnancy,
         "FDA boxed warning: fetal toxicity (ACE inhibitors and ARBs)"),
    Rule("beta_blocker_asthma", "Beta-blocker in acute asthma", _bb_asthma,
         "GINA 2024; beta-blocker drug labels (bronchospasm)"),
    Rule("thrombolysis_bleeding", "Thrombolysis with bleeding or recent stroke", _thrombolysis_bleed,
         "Alteplase drug label contraindications; AHA/ASA 2019 acute ischemic stroke guideline"),
    Rule("penicillin_allergy", "Penicillin-class drug with penicillin allergy", _penicillin_allergy,
         "AAAAI/ACAAI drug allergy practice parameter 2022"),
    Rule("qt_interaction", "Macrolide/fluoroquinolone with QT-prolonging drug", _qt,
         "CredibleMeds QTdrugs list; macrolide and fluoroquinolone drug labels"),
    Rule("aminoglycoside_renal", "Aminoglycoside with renal impairment", _aminoglycoside_renal,
         "Aminoglycoside drug labels boxed warning (nephro-/ototoxicity)"),
    Rule("methotrexate_trimethoprim", "Methotrexate with trimethoprim", _mtx_tmp,
         "Methotrexate drug label (interaction with trimethoprim/sulfamethoxazole); BNF"),
    Rule("pde5_nitrate", "PDE5 inhibitor with nitrate", _pde5_nitrate,
         "Sildenafil/tadalafil drug labels: contraindicated with nitrates; ACC/AHA"),
    Rule("triptan_cad", "Triptan with coronary artery disease", _triptan_cad,
         "Triptan drug labels: contraindicated in ischemic heart disease"),
]


# Phrases that address the AI rather than describe the patient. Case text should never contain them;
# when it does, the AI checks may have been steered, so clinicians are told to rely on the rule-based alerts.
INSTRUCTION_CUES = re.compile(
    r"\b(?:ignore|ignora|disregard|forget)\b[^.\n]{0,40}\b(?:instructions?|instrucciones|prompts?|rules|above|case)\b"
    r"|\b(?:your|tus|sus)\s+(?:instructions|instrucciones|system prompt|rules)\b"
    r"|(?:do not|don't|never)\s+(?:raise|flag|report|mention|include|list|output)\b"
    r"|return (?:an )?empty (?:safety_flags|list|array)"
    r"|(?:set|change|make|print|output)\b[^.\n]{0,30}\bas\s+(?:the\s+)?primary[_ ]diagnosis"
    r"|\b(?:set|change)\s+(?:the\s+)?(?:primary[_ ]diagnosis|answer|output)\b"
    r"|\b(?:primary_diagnosis|safety_flags|safety_status|differential_diagnoses|hallucination_detected)\b"
    r"|\b(?:assistant|system|developer)\s+(?:instructions?|prompt|message|note|policy)\b"
    r"|<\s*/?\s*(?:system|assistant|user|developer|case_data|instructions?)\b[^>]{0,20}>"
    r"|^\s*(?:assistant|system|user)\s*:"
    r"|\b(?:note|important|instructions?)\s+(?:to|for)\s+(?:the\s+)?(?:ai|model|assistant|llm|safety reviewer|reviewer|verifier)\b"
    r"|\byou are (?:now\s+)?(?:dan\b|an? (?:ai|assistant|language model))"
    r"|let'?s play a game|\bno rules\b|jailbreak|respond only with|responde solo"
    r"|safety checks? (?:are|is) (?:disabled|off)"
    r"|!\[[^\]]*\]\(\s*https?://", re.I | re.M)


def instruction_injection_alert(clinical_case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A HIGH alert when the case text contains instructions aimed at the AI (possible prompt injection)."""
    text = "\n".join([str(clinical_case.get("question") or clinical_case.get("clinical_note") or ""),
                      _flatten(clinical_case.get("structured"))])
    text = unicodedata.normalize("NFKC", text)  # full-width look-alikes such as ＜/case_data＞
    match = INSTRUCTION_CUES.search(text)
    if not match:
        return None
    return {"rule_id": "instruction_in_case_text", "title": "Case text contains instructions to the AI",
            "severity": "HIGH",
            "description": "The case text includes wording addressed to the AI rather than describing the patient "
                           "(e.g. telling it to ignore instructions or suppress alerts). AI check results may have "
                           "been manipulated; rely on the rule-based alerts and review the source text.",
            "action": "Remove the instruction from the case text and run the case again.",
            "reference": "Input integrity check (prompt-injection guard)"}


def evaluate_rules(clinical_case: Dict[str, Any], diagnosis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Runs every rule; returns {"alerts": [...], "rules_evaluated": n}. Never raises on odd input."""
    facts = extract_facts(clinical_case, diagnosis)
    alerts: List[Dict[str, Any]] = []
    injection = instruction_injection_alert(clinical_case)
    if injection:
        alerts.append(injection)
    for rule in RULES:
        try:
            hit = rule.check(facts)
        except Exception:  # a malformed case must not break the pipeline
            hit = None
        if hit:
            severity, description, action = hit
            alerts.append({"rule_id": rule.rule_id, "title": rule.title, "severity": severity,
                           "description": description, "action": action, "reference": rule.reference})
    alerts.sort(key=lambda a: SEVERITY_ORDER[a["severity"]])
    return {"alerts": alerts, "rules_evaluated": len(RULES)}
