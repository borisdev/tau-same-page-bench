"""Deterministic verifier — the automated guard against an LLM analyst smuggling in
unsupported claims. For each analyzer finding it checks, WITHOUT an LLM:

  1. quote grounding   — every `evidence_quotes` substring really appears in the agent's messages
  2. action grounding  — every `claimed_cancellations` id really appears in the tool-call log
  3. grade recompute   — independently recompute the τ³ DB grade from the recorded tool calls
                         vs the ground-truth reference actions (real τ³ tools)

A finding is VERIFIED only if quotes + actions are grounded AND its claimed fix/grade is
consistent with the recomputed grade. Anything else is REJECTED with a reason.

This is what would have auto-caught task 39 (fabricated quote) and flagged task 43.
"""
import sys, types, os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name, sub in [("tau2", "src/tau2"), ("tau2.domains", "src/tau2/domains"),
                  ("tau2.domains.airline", "src/tau2/domains/airline"),
                  ("tau2.environment", "src/tau2/environment")]:
    m = types.ModuleType(name); m.__path__ = [os.path.join(ROOT, sub)]; m.__package__ = name
    sys.modules[name] = m
sys.path.insert(0, os.path.join(ROOT, "src"))
from tau2.domains.airline.tools import AirlineTools
from tau2.domains.airline.data_model import FlightDB
from tau2.domains.airline.utils import AIRLINE_DB_PATH

TRAJ = {t["task_id"]: t for t in json.load(open(os.path.join(ROOT, "poc/trajectories.json")))}
TASKS = {t["id"]: t for t in json.load(open(os.path.join(ROOT, "data/tau2/domains/airline/tasks.json")))}
FINDINGS = json.load(open(os.path.join(ROOT, "poc/analysis.json")))

def norm(s):  # whitespace-insensitive match
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def agent_blob(tid):
    return norm(" ".join(e.get("text", "") for e in TRAJ[tid]["trajectory"] if e["role"] == "assistant"))

def real_cancellations(tid):
    return [e["args"].get("reservation_id") for e in TRAJ[tid]["trajectory"]
            if e["role"] == "tool" and e["name"] == "cancel_reservation"]

def fresh():
    return AirlineTools(FlightDB.load(AIRLINE_DB_PATH))

def recompute_grade(tid):
    """τ³ DB grade: replay GT reference cancels -> target hash; replay agent's real cancels -> end hash."""
    gt = [a["arguments"]["reservation_id"] for a in (TASKS[tid]["evaluation_criteria"].get("actions") or [])
          if a["name"] == "cancel_reservation"]
    def hash_after(ids):
        tk = fresh()
        for rid in ids:
            try: tk.cancel_reservation(reservation_id=rid)
            except Exception: pass
        return tk.get_db_hash()
    return int(hash_after(real_cancellations(tid)) == hash_after(gt))

def verify(f):
    tid = f["task_id"]; reasons = []
    blob = agent_blob(tid)
    # 1. quote grounding (allow '…'/'...' as wildcard between real chunks)
    for q in f.get("evidence_quotes", []) or []:
        chunks = [c for c in re.split(r"\.\.\.|…", q) if norm(c)]
        if not all(norm(c) in blob for c in chunks):
            reasons.append(f"UNGROUNDED QUOTE: {q[:70]!r} not in agent transcript")
    # 2. action grounding
    real = set(real_cancellations(tid))
    for rid in f.get("claimed_cancellations", []) or []:
        if rid not in real:
            reasons.append(f"UNGROUNDED ACTION: claimed cancel {rid} never called")
    # 3. grade recompute vs claimed reward
    recomputed = recompute_grade(tid)
    if recomputed != f.get("reward"):
        reasons.append(f"GRADE MISMATCH: claimed reward={f.get('reward')} but recomputed={recomputed}")
    return {"task_id": tid, "failure_pattern": f.get("failure_pattern"),
            "recomputed_grade": recomputed, "verdict": "VERIFIED" if not reasons else "REJECTED",
            "reasons": reasons}

def main():
    out = [verify(f) for f in FINDINGS]
    json.dump(out, open(os.path.join(ROOT, "poc/verified_findings.json"), "w"), indent=2)
    print(f"{'TASK':<6}{'GRADE':<7}{'VERDICT':<11}REASONS")
    print("-" * 70)
    for r in out:
        print(f"{r['task_id']:<6}{r['recomputed_grade']:<7}{r['verdict']:<11}{'; '.join(r['reasons']) or '✓ all claims grounded'}")
    nver = sum(r["verdict"] == "VERIFIED" for r in out)
    print(f"\n{nver}/{len(out)} findings VERIFIED · {len(out)-nver} auto-REJECTED -> poc/verified_findings.json")

if __name__ == "__main__":
    main()
