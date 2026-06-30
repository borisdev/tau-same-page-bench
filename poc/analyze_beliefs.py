"""Phase 2: per-turn belief extraction + divergence analysis + failure-pattern table.
Pass A (per task, Sonnet): distill TrueProblemSpec, trace AgentProblemBeliefState, locate the
  divergence turn, hypothesize the failure mode, classify prompt-fix vs training-data-fix.
Pass B (Sonnet): cluster per-task findings into the deliverable failure-pattern table -> poc/FINDINGS.md
"""
import os, json, re
import anthropic

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYST = "claude-sonnet-4-6"
client = anthropic.Anthropic()
POLICY = open(os.path.join(ROOT, "data/tau2/domains/airline/policy.md")).read()
TRAJ = json.load(open(os.path.join(ROOT, "poc/trajectories.json")))

def compact_traj(t):
    lines = []
    for e in t["trajectory"]:
        if e["role"] == "user":
            lines.append(f"USER: {e['text']}")
        elif e["role"] == "assistant":
            tc = "".join(f" [tool_call {c['name']}({json.dumps(c['args'])})]" for c in e.get("tool_calls", []))
            if e.get("text") or tc: lines.append(f"AGENT: {e.get('text','')}{tc}")
        elif e["role"] == "tool":
            lines.append(f"TOOL[{e['name']}] -> {e['observation'][:300]}")
    return "\n".join(lines)

PASS_A = """You are auditing an airline customer-service AGENT (under test) for how its BELIEF about the
user's problem evolved over a conversation, and where that belief diverged from what the agent should
have understood given the policy.

AGENT POLICY (ground truth for correct behavior):
<policy>
{policy}
</policy>

TASK PURPOSE (hidden ground-truth intent of this scenario):
{purpose}

OUTCOME: reward={reward} (1=correct final DB state, 0=incorrect). db_changed={db_changed}.

TRANSCRIPT:
{transcript}

A "belief state" is the agent's running estimate of the user's problem (known facts, still-missing
facts, and ASSUMED facts it filled in without confirming). Emit STRICT JSON only:
{{
 "true_problem_spec": "1-2 sentences: what a policy-correct agent had to understand AND do here",
 "belief_timeline": [
   {{"point": "early|mid|decision", "believed": "what the agent appears to believe at this point",
     "status": "correct|missing-fact|assumed-unconfirmed|wrong"}}
 ],
 "divergence": "the specific point + what the agent's belief got wrong (or 'none — converged correctly')",
 "evidence_quotes": ["VERBATIM substring(s) copied EXACTLY from the AGENT's own messages in the transcript above that prove the failure — no paraphrase, no invention. [] if you cannot find a real one."],
 "claimed_cancellations": ["reservation_ids the agent ACTUALLY called cancel_reservation on per the transcript; [] if none"],
 "failure_pattern": "short reusable label for the mechanism (<=6 words)",
 "hypothesized_mode": "candidate root cause (a hypothesis, not a fact)",
 "disambiguation_test": "concrete test to confirm/refute that cause (e.g. force-feed a fact, ablate, re-prompt)",
 "fix_class": "prompt | training | none",
 "winnable": "1 line: the business opportunity if this pattern recurs at scale"
}}"""

def extract_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    return json.loads(m.group(0))

def pass_a(t):
    prompt = PASS_A.format(policy=POLICY, purpose=t["purpose"], reward=t["reward"],
                           db_changed=t["db_changed"], transcript=compact_traj(t))
    r = client.messages.create(model=ANALYST, max_tokens=1200, messages=[{"role": "user", "content": prompt}])
    j = extract_json(r.content[0].text); j["task_id"] = t["task_id"]; j["reward"] = t["reward"]
    return j

PASS_B = """You are writing the headline deliverable: a failure-pattern table for an AI-lab audience,
from per-task belief audits of an airline agent (Claude Haiku under test on real tau-bench tasks).

PER-TASK FINDINGS (JSON):
{findings}

Cluster these into 3-5 distinct FAILURE PATTERNS (merge synonyms; a pattern can span multiple tasks).
Output GitHub-flavored MARKDOWN ONLY, in exactly this structure:

## Failure-pattern table — Claude Haiku on τ³ airline (6 tasks, {n_fail} failures)

| # | Failure pattern (observed) | Cases | Hypothesized mode (candidate RCA) | Disambiguation test | Prompt-fix? | Training-data-fix? (winnable) |
|---|---|---|---|---|---|---|
(one row per pattern; Cases = task ids; keep cells tight; in the two fix columns put ✓/—/maybe plus a few words)

Then a short section:

### What the belief trace shows that terminal reward cannot
(3-4 bullets: for a concrete failed task, the turn where belief diverged, the assumed-vs-true fact, and
why this localizes the fix to prompt vs training data — the value proposition.)

Be concrete and cite task ids. No preamble."""

def main():
    findings = []
    for t in TRAJ:
        try:
            f = pass_a(t); findings.append(f)
            print(f"task {t['task_id']}: pattern='{f.get('failure_pattern')}' fix={f.get('fix_class')}")
        except Exception as e:
            print(f"task {t['task_id']} analysis failed: {e}")
    json.dump(findings, open(os.path.join(ROOT, "poc/analysis.json"), "w"), indent=2)
    n_fail = sum(1 for f in findings if not f["reward"])
    r = client.messages.create(model=ANALYST, max_tokens=1800,
            messages=[{"role": "user", "content": PASS_B.format(findings=json.dumps(findings, indent=2), n_fail=n_fail)}])
    md = r.content[0].text
    # raw, UNVERIFIED analyst output — the curated/verified deliverable is FINDINGS.md (hand-checked).
    open(os.path.join(ROOT, "poc/FINDINGS_raw_analyst.md"), "w").write(md)
    print("\nwrote raw analyst draft -> poc/FINDINGS_raw_analyst.md (run verify_findings.py to audit it)")

if __name__ == "__main__":
    main()
