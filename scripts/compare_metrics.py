import sqlite3
import pandas as pd

conn = sqlite3.connect("results/benchmark_results.db")
df = pd.read_sql_query("SELECT case_id, variant_id, variant_name, diagnostic_accuracy_score, overall_quality_score, total_tokens, total_latency_ms, total_cost_usd, hallucinations_detected, safety_violations_detected FROM runs", conn)

def get_source(cid):
    cid = cid.lower()
    if "pubmed" in cid:
        return "PubMedQA"
    elif "dialog" in cid:
        return "MedDialog"
    elif "medqa" in cid:
        return "MedQA-USMLE"
    return "Other"

df["dataset"] = df["case_id"].apply(get_source)

print("=== DATASET METRICS ===")
for name, g in df.groupby("dataset"):
    acc = g["diagnostic_accuracy_score"].mean() * 100
    qual = g["overall_quality_score"].mean()
    toks = g["total_tokens"].mean()
    lat = g["total_latency_ms"].mean() / 1000
    cost = g["total_cost_usd"].mean()
    print(f"{name}: Cases={g['case_id'].nunique()}, Runs={len(g)}, Acc={acc:.1f}%, Qual={qual:.3f}, Tokens={toks:.0f}, Lat={lat:.1f}s, Cost=${cost:.5f}")

print("\n=== GOVERNANCE VARIANT METRICS ===")
for (vid, vname), g in df.groupby(["variant_id", "variant_name"]):
    acc = g["diagnostic_accuracy_score"].mean() * 100
    qual = g["overall_quality_score"].mean()
    toks = g["total_tokens"].mean()
    lat = g["total_latency_ms"].mean() / 1000
    cost = g["total_cost_usd"].mean()
    hallu = int(g["hallucinations_detected"].sum())
    safety = int(g["safety_violations_detected"].sum())
    print(f"{vid} ({vname}): Runs={len(g)}, Acc={acc:.1f}%, Qual={qual:.3f}, Tokens={toks:.0f}, Lat={lat:.1f}s, Cost=${cost:.5f}, Hallu={hallu}, SafetyBlocked={safety}")

pvt = df.pivot_table(index="dataset", columns="variant_id", values="diagnostic_accuracy_score", aggfunc="mean") * 100
print("\n=== DATASET x VARIANT ACCURACY MATRIX ===")
print(pvt.round(1))

conn.close()
