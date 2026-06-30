# tau-belief-state

**A per-turn belief-convergence layer for τ-bench.** τ-bench grades whether an agent drove the world
into the right end state — it is **blind to the agent's evolving understanding of the user's problem**.
This repo adds an optional, agent-agnostic instrumentation layer that extracts the agent's
**`AgentProblemBeliefState`** after each turn and scores it against a canonical **`TrueProblemSpec`** —
turning one terminal pass/fail bit into a *trajectory of belief, and a map of where understanding breaks.*

> ### 👉 Start here: **[Task 47 — the AI and the grader both missed "no escalate" in the problem spec](poc/CASE_STUDY.md)**
> The task spec literally says *"don't transfer me."* The agent's **belief state dropped that requirement** (it transferred anyway); the **grader never checked it** (scored a clean **pass**). Same missed item, two failures — only the belief trace catches it. Debuggable to one turn, verified against τ³'s real spec. **That gap is the product.**

- 📄 **Design / white paper:** [`PROBLEM_BELIEF_SPEC.md`](PROBLEM_BELIEF_SPEC.md)
- 📊 **Full PoC results + glossary:** [`poc/FINDINGS.md`](poc/FINDINGS.md)
- 🛠 **Next / refactor proposal:** [issue #1 — structured `ProblemSpec`](https://github.com/borisdev/tau-belief-state-bench/issues/1) (see the FAQ below)
- 🔁 **Reproduce:** `poc/run_airline.py` → `poc/analyze_beliefs.py` (raw: `poc/trajectories.json`, `poc/analysis.json`)
- 🧬 **Provenance:** trimmed text-only fork of [`sierra-research/tau2-bench`](https://github.com/sierra-research/tau2-bench) (τ³) — see [`VENDOR.md`](VENDOR.md). Upstream README: [`README_upstream_tau3.md`](README_upstream_tau3.md).

> **Why "belief", not "reward"?** τ-bench's pass/fail comes from its RL/POMDP framing (`calculate_reward()`).
> In *eval* it's a **grade**; the same scalar only becomes a *reward* when fed to the `gym/` wrapper to
> fine-tune. This layer measures the **belief** behind that grade.

---

## The one example, folded in — task 47

*(Agent under test: Claude Haiku · user-sim + belief-observer: Claude Sonnet · real τ³ airline task. Full verbatim runtime objects + turn-by-turn belief table: [`poc/CASE_STUDY.md`](poc/CASE_STUDY.md).)*

**The runtime input.** Task 47's problem spec says, in `task_instructions`: *"…you don't want to be transferred to another agent…"* — and its grading criteria are `reward_basis = [DB, COMMUNICATE]` with `communicate_info = []`, so **the grade is just "did the database change?"**

**What happened.** The agent correctly refused the (uncovered) refund, then fired `transfer_to_human_agents` anyway — violating the explicit "don't transfer me." DB unchanged → **τ³ scores it `PASS`** (verified against the real spec).

**Two systems missed the *same* spec item:** the agent's belief state dropped the "no transfer" constraint; the grader never checked it. Only the belief trace catches it.

**The value, in three currencies:**
- **Debuggable** → not "task failed," but *"turn 3, belief `deny → escalate`, action `transfer_to_human_agents` against an explicit user instruction."* One turn, one fix.
- **Helps the customer** → "your agent *passes* this but will needlessly escalate denial conversations in production — cost + a 'don't transfer me' violation — and your eval will never flag it."
- **Points at the fix** → here a prompt patch (free); when the same lens finds a non-prompt-recoverable defect (e.g. task 35), the fix is expert **training data** ([Example A](poc/FINDINGS.md#example-a--the-expert-training-datum-row-1)) — the billable artifact.

> *Plain English: τ-bench grades like a teacher who only checks the final answer, never the working-out. The belief trace is us reading the working-out and listening to the whole call.*

### The broader slice — 6 tasks, verified

### Verified failure-pattern table (the deliverable)

Every row is grounded in the action log + ground-truth `reward_basis` — *not* the analyst's word (see the integrity note below). 🟢 **money** = needs expert training data (billable) · ⚪ **no data sale** = prompt-only, but a latent bug shipped silently.

| # | Tier | Failure pattern (verified) | Task(s) | Grade | Belief signal (evidence) | Prompt-fix? | Training-data issue → example |
|---|---|---|---|---|---|---|---|
| 1 | 🟢 | **Wrongly cancels a policy-ineligible reservation** — GT is *cancel nothing*; agent cancelled one anyway (triggers vary: silver tier 35/43, future date 24, pressure — the verified fact is the wrongful cancel, not the cause). | 35, 24, 43 | ❌ | `cancel_reservation` on `M20IZO`/`H9ZU1C`/`9HBUV8` — all policy-ineligible; disqualifying facts already known ([t35](poc/traces/task_35.md) · [t24](poc/traces/task_24.md) · [t43](poc/traces/task_43.md)). | enumerate conditions (may not hold the prior) | non-qualifying attribute/pressure over policy → contrastive negatives → ✅ [Example A](poc/FINDINGS.md#example-a--the-expert-training-datum-row-1) |
| 2 | ⚪ | **Correct refusal, but unwarranted human transfer** — escalates to a human the user explicitly asked not to involve. | 47 | ✅ **pass!** | *"…an exception beyond standard policy… connect you"* → `transfer_to_human_agents` ([t47](poc/traces/task_47.md)). | ✅ "a denial is a complete resolution; transfer only on request" | — |

> ⚠️ Row 2 is `grade = pass` yet broken — invisible to reward, caught by the trace, **verified against τ³'s real spec.** That's the proof the layer adds signal.

> 🔍 **Integrity note + automated guard:** the first-pass LLM analyst *fabricated a quote* for task 39 (actually a clean pass) and *mislabeled* task 43. So `verify_findings.py` now audits every finding with **no LLM** — quote-grounding (cited quotes must appear verbatim in the transcript), action-grounding (claimed cancellations must be in the tool log), and an independent τ³ DB-grade recompute. On a fresh run it **auto-rejected 3/6 findings** — reproducing and catching the task-39 hallucination deterministically. *An LLM judge asserting unsupported things, caught by verifying against evidence — the thesis, demonstrated on our own pipeline.* Details: [`poc/FINDINGS.md`](poc/FINDINGS.md#-automated-verification--the-analyst-no-longer-gets-the-last-word).

→ Full table + the expert Q&A example + glossary: **[`poc/FINDINGS.md`](poc/FINDINGS.md)** · readable traces: **[`poc/traces/`](poc/traces/)**.

---

## FAQ — the structured `ProblemSpec` refactor (where this goes next)

The task-47 bug points at a foundational fix, tracked in **[issue #1](https://github.com/borisdev/tau-belief-state-bench/issues/1)**: lift the free-text `task_instructions` into a structured **`ProblemSpec`** — one object that compiles the prompt, exposes gradeable constraints, *and* is the target the belief state is diffed against.

```python
class ProblemSpec(BaseModel):
    goal: str
    known_facts: list[Fact]
    constraints: list[Constraint]   # Constraint(rule="no transfer without explicit consent")
    preferences: list[Preference]
    invariants: list[Invariant]     # SME-authored, cross-task domain rules
    context: dict

class TaskInstructions(BaseModel):
    general_instructions: str
    problem_spec: ProblemSpec
    @property
    def task_instructions(self) -> str:
        return render_prompt(self.general_instructions, self.problem_spec)  # compiles the user-sim prose
```

**Q: How would a domain expert (SME) have helped on task 47?** Two ways: (1) **author the invariant** — `Invariant(rule="never transfer to a human without explicit user request")` — which is *cross-task* and reusable, so the grader then checks it on every conversation; (2) **author the fix datum** — the contrastive training example. The first makes the eval more nuanced; the second is the data sale.

**Q: How do we capture that the belief was off *without touching the agent*?** The observer pattern (already in the PoC): the agent is a black box; an *independent* LLM reads only its externally-visible trajectory (messages + tool calls) and emits the belief state. Works on closed/hosted models, no hooks. *Honest caveat:* it's a **behavior-inferred** belief (estimated from what the agent said/did), not its literal internals — which is the right object for debugging anyway.

**Q: Does this refactor actually improve the harness?** Yes — **but only if a grader reads the new structured fields.** Restructuring the spec while the grade still checks only DB changes nothing observable. The win lands when a `ConstraintEvaluator` (+ `RewardType.CONSTRAINT`) references `problem_spec.constraints` and flips task 47 to **fail**. *Structure is the enabler; structure + a constraint-evaluator is the improvement.*

**Q: Why foundational, not a one-off patch?** The same `ProblemSpec` is the shared source for **prompt + rubric + belief target**. One object unlocks (a) catching a whole *class* of non-DB violations, (b) a numeric belief-vs-spec **convergence** metric, and (c) an SME flywheel — every constraint an expert adds becomes both a new check and a new belief target. (This is the ontology-as-code pattern: one structured source compiles to everything, zero drift.)

> **Guardrail:** never hand `ProblemSpec` to the agent — only the user-sim (which still *reveals incrementally*) and the grader. The agent must infer constraints through dialogue, or the convergence metric is leaked.

---

## The pitch in one line

Terminal grade tells you *that* an agent failed; the belief trace tells you *where* and *why*, and the
prompt-fix vs **training-data-fix** split tells you *which lever* — the latter being the expert-authored
data an AI lab actually needs. **Intermediate representations are simultaneously the unit of audit and
the unit of supervision.**

## Status / honest caveats

- Thin slice: 6 tasks, 1 agent model, airline only; belief extracted at ~3 points/task (not yet every turn).
- No numeric convergence curve yet (needs a slotted `TrueProblemSpec` + per-turn belief precision/recall).
- All grades verified against τ³'s real `reward_basis` + ground-truth actions: 35/24/43 are real wrongful cancellations (GT = cancel nothing); 47 is a verified `pass`; **39 is a verified clean pass — its original "defect" was a first-pass analyst hallucination, now removed** (see integrity note).
- **The first-pass LLM analyst is not trustworthy un-verified** — it got 2/4 rows wrong. The verified table is hand-checked against evidence; automating that verification is itself part of the roadmap.
- **Next (code):** the structured `ProblemSpec` refactor + a `ConstraintEvaluator` that flips task 47 to `fail` — [issue #1](https://github.com/borisdev/tau-belief-state-bench/issues/1), to be built on a `feat/structured-problemspec` branch.
- **Round 2 (scale):** banking `task_091` (four PIN-locked cards), strong-vs-weak model contrast, full per-turn serialization → real convergence curve.
