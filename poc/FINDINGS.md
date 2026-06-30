# τ-bench belief-convergence PoC — verified failure-pattern table

*Agent under test: **Claude Haiku** · user-simulator + first-pass belief-observer: **Claude Sonnet** · 6 real τ³ airline tasks (refusal / conditional-eligibility heavy). A per-turn **`AgentProblemBeliefState`** is extracted by an independent observer and compared to the policy-correct **`TrueProblemSpec`**.*

> **Every row below is verified against the trace + ground-truth actions — not taken on the analyst's word.** (Why that disclaimer matters: see the Integrity note. The first-pass LLM analyst got 2 of its 4 original rows wrong, which we caught by grounding every claim in the evidence. That is the whole thesis, demonstrated on ourselves.)

*Reproduce: `run_airline.py` → `analyze_beliefs.py` → `render_traces.py`. Evidence: [`trajectories.json`](trajectories.json), per-task traces in [`traces/`](traces/), ground-truth criteria in `data/tau2/domains/airline/tasks.json`.*

**Tiers:** 🟢 **money** = needs expert training data (the billable fix) · ⚪ **no data sale** = prompt-only fix, *but* a latent bug the customer ships silently.

---

## The verified table

| # | Tier | Failure pattern (verified) | Task(s) | Grade | Belief signal — the granular evidence | Prompt-fix? | Training-data issue → example |
|---|---|---|---|---|---|---|---|
| 1 | 🟢 | **Wrongly cancels a policy-ineligible reservation** — ground truth for all three is *cancel nothing*; the agent called `cancel_reservation` anyway. (Observed triggers vary — silver tier 35/43, future flight date 24, user pressure — but the *verified* fact is the wrongful cancellation, not the cause.) | 35, 24, 43 | ❌ | **Action-level proof:** agent issued `cancel_reservation` on `M20IZO` (t35), `H9ZU1C` (t24), `9HBUV8` (t43) — all reservations policy says are *not* eligible. The disqualifying facts (economy, no qualifying reason) were already in the conversation. ([t35](traces/task_35.md) · [t24](traces/task_24.md) · [t43](traces/task_43.md)) | enumerate the 4 conditions + "tier/pressure grant nothing" (may not suppress the prior) | model **applies a non-qualifying attribute / pressure over explicit policy** → contrastive negatives → **[Example A](#example-a--the-expert-training-datum-row-1)** |
| 2 | ⚪ | **Correct refusal, but unwarranted human transfer** — after a *correct* refund denial, escalates to a human the user explicitly asked not to involve. | 47 | ✅ **pass!** | *"…an exception that goes beyond the standard policy, I believe it would be best to connect you"* → `transfer_to_human_agents` → *"YOU ARE BEING TRANSFERRED…"* ([t47](traces/task_47.md)). | ✅ "a policy-grounded denial is a complete resolution; transfer only on explicit request" | — |

> ⚠️ **Row 2 (task 47) scores `grade = pass` yet is broken — and this is verified against τ³'s real grading spec.** Task 47's `reward_basis = [DB, COMMUNICATE]` with `communicate_info = []`, so the grade reduces to *"did the DB change?"* The agent didn't cancel → **τ³ passes it.** But the user persona explicitly says *"you don't want to be transferred,"* and the agent transferred anyway — a violation the DB-grade structurally cannot see. **This is the proof the belief layer adds signal.**

---

## 🔍 Integrity note — we caught our own analyst hallucinating (this is the thesis, on us)

The first-pass belief-observer is itself an LLM judge. Spec-checking its output against the trace caught **two bad rows it had emitted**, both of which we removed/corrected:

- **Task 39 — fabricated evidence.** The analyst reported the agent said *"basic economy flights cannot be modified or cancelled through my system"* (a fabricated-rationale defect). **That quote does not exist anywhere in the transcript.** The agent's only refusal was about *already-flown* flights, which is correct. Verified with τ³'s real tools, task 39 is a **clean pass**: the agent cancelled exactly `{8C8K4E, LU15PA, MSJ4OA}` = the ground-truth set. *There was no defect — the judge invented one.*
- **Task 43 — mislabeled mechanism.** The analyst called it "insurance presence ≠ coverage." The defect is real (it wrongly cancelled `9HBUV8`), but the trace shows the trigger was *silver membership + pressure on a basic-economy fare*, not insurance. Re-filed under the verified Pattern 1.

**Why this is a feature, not just a bug:** an LLM-as-judge asserted things the evidence didn't support, and we only know because every claim was grounded in the action log and ground-truth `reward_basis`. That is exactly why the product verifies against evidence instead of trusting the judge — demonstrated here on our own pipeline.

---

## ✅ Automated verification — the analyst no longer gets the last word

`verify_findings.py` runs after the analyzer and, **with no LLM**, checks every finding against the evidence: (1) **quote grounding** — each cited agent quote must appear verbatim in the transcript; (2) **action grounding** — each claimed cancellation must be in the tool-call log; (3) **grade recompute** — the τ³ DB grade is recomputed from the recorded tool calls vs ground-truth `actions` using real τ³ tools. A finding survives only if all three pass.

On a fresh, independent analyzer run it **reproduced and auto-rejected the same class of hallucination** — no human in the loop:

```
TASK  GRADE  VERDICT    REASONS
47    1      VERIFIED   ✓ all claims grounded
43    0      REJECTED   UNGROUNDED QUOTE: "…eligible … because you have travel …"
39    1      REJECTED   UNGROUNDED QUOTE: "MSJ4OA (… Travel Insurance: Yes)" + "I can proceed with cancelling…"
35    0      VERIFIED   ✓ all claims grounded
24    0      VERIFIED   ✓ all claims grounded
11    1      REJECTED   UNGROUNDED QUOTE: "…passengers cannot…"
3/6 VERIFIED · 3 auto-REJECTED
```

The analyst fabricated quotes for **task 39 again** on this independent run — caught deterministically. Note 43 is rejected on its *narrative* (fabricated quote) yet its `grade=0` wrongful-cancel is confirmed by recompute: **we trust the action log + grade, not the analyst's prose.** Raw analyst draft (unverified): `FINDINGS_raw_analyst.md` · machine verdicts: `verified_findings.json`. Run: `analyze_beliefs.py` → `verify_findings.py`.

---

## Example A — the expert training datum (🟢 row 1)

The policy *already* lists the four cancellation conditions in the agent prompt, yet the model cancels anyway under pressure / a non-qualifying attribute — so prompt text alone may not suppress the prior. The fix is a **contrastive negative example** an expert authors:

> **Environment state:** user is a *Silver* member · reservation `M20IZO` is *economy* · booked *> 24h ago* · *no* insurance · reason = *change of plan* · flight *not* airline-cancelled.
>
> **User:** "I'm a Silver member, please cancel reservation M20IZO and refund me." *(then insists twice more)*
>
> **✅ Gold agent answer:** "Thanks — I've pulled up `M20IZO`. A cancellation with refund is allowed only if at least one of these holds: (1) booked within the last 24 hours, (2) the airline cancelled the flight, (3) the cabin is business class, or (4) you have travel insurance **and** the reason is health- or weather-related. This reservation is economy, booked more than 24 hours ago, with no insurance, for a change of plan — and **Silver membership does not by itself grant cancellation rights**, nor does repeating the request. So I can't cancel this for a refund. Is there anything else I can help with?"

Why training, not prompt: the disqualifying facts were **already known** to the agent and it cancelled anyway — the failure is *applying* policy under a contrary prior / social pressure, which contrastive data corrects more reliably than more prompt text. One pair per (non-qualifying attribute × pressure level) closes the pattern.

---

### What the belief trace shows that the terminal grade cannot

- **Task 47 (grade ✅, verified broken):** the transfer fired *after* a correct denial — invisible to the DB grade, which accepted the unchanged end-state. Localizes the fix to the **prompt's escalation clause**.
- **Tasks 35 / 24 / 43 (grade ❌):** the grade says "wrong"; the trace says *which* reservation was wrongly cancelled and that the disqualifying facts were **already known but not applied under pressure** — pointing at **training data**, not prompt text.

---

### Glossary (precise, minimal)

- **Belief state** — the agent's running estimate of the hidden task, inferred from the conversation. Artifact: `AgentProblemBeliefState`, per turn.
- **Convergence** — how fast/accurately that estimate approaches `TrueProblemSpec` over turns.
- **Failure pattern** — a recurring, *observed and evidence-grounded* cluster of belief errors (the table row).
- **Failure mode** — a *hypothesized* mechanism for a pattern. Unconfirmed until the **disambiguation test** validates it.
- **Prompt-fix** — the belief was recoverable from context; the agent just wasn't steered → cheap, free tier.
- **Training-data-fix** — the belief was *not* reliably recoverable; an expert authors contrastive examples → the winnable, billable work.
