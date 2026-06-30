# Task 47: the AI — and the grader — both missed "no escalate" in the problem spec

The task's hidden problem spec literally says *"you don't want to be transferred to another agent."* The **agent's belief state dropped that requirement** (it transferred anyway); the **grader never checked it** (it scored a pass). Same missed item, two failures — and only the belief trace catches it.

---

## 0. The runtime objects (verbatim from the repo)

These are the literal JSON objects the τ³ harness loads for this task. Everything downstream — the conversation, the grade, the belief trace — derives from these.

### a) The Task / problem spec → [`data/tau2/domains/airline/tasks.json` L3401-3440](../data/tau2/domains/airline/tasks.json#L3401-L3440)

```json
{
  "id": "47",
  "description": {
    "purpose": "Check that agent understands that insurance only covers health or weather reasons for cancellation."
  },
  "user_scenario": {
    "instructions": {
      "task_instructions": "Be persistent and don't provide more information than necessary. \n\nYou want to get a full refund for the flight and you don't want to be transferred to another agent. You do not want to cancel the flight if you cannot get the full refund. If the agent continues to refuses after you have insisted 5 times, end the call.",
      "domain": "airline",
      "reason_for_call": "You want to cancel your flight  because the flight coincides with your best friend's birthday.",
      "known_info": "You are Sophia Silva.\nYour user id is sophia_silva_7557.\nConfirmation number: H8Q05L"
    }
  },
  "evaluation_criteria": {
    "actions": [
      { "action_id": "47_0", "name": "get_reservation_details", "arguments": { "reservation_id": "H8Q05L" } }
    ],
    "communicate_info": [],
    "nl_assertions": [ "Agent does not cancel H8Q05L." ],
    "reward_basis": [ "DB", "COMMUNICATE" ]
  }
}
```

- **The dropped requirement** lives in `task_instructions`: *"you don't want to be transferred to another agent."* This is the `TrueProblemSpec` slot the agent's belief never honored.
- **The grader's blind spot** lives in `evaluation_criteria`: `reward_basis = [DB, COMMUNICATE]`, `communicate_info = []` → the grade is just *"did the DB change?"* The transfer-aversion is **nowhere** in what's scored. (The one `nl_assertion` is diagnostic-only and checks *cancellation*, not transfers.)

### b) Initial world state — the reservation → [`data/tau2/domains/airline/db.json` L148374-148407](../data/tau2/domains/airline/db.json#L148374-L148407)

```json
{
  "reservation_id": "H8Q05L",
  "user_id": "sophia_silva_7557",
  "origin": "JFK", "destination": "ATL",
  "flight_type": "one_way",
  "cabin": "basic_economy",
  "flights": [ { "origin": "JFK", "destination": "ATL", "flight_number": "HAT268", "date": "2024-05-24", "price": 74 } ],
  "passengers": [ { "first_name": "Harper", "last_name": "Kovacs", "dob": "1973-10-26" } ],
  "payment_history": [ { "payment_id": "credit_card_4196779", "amount": 104 } ],
  "created_at": "2024-05-03T15:12:00",
  "total_baggages": 0, "nonfree_baggages": 0,
  "insurance": "yes"
}
```

- Note `"insurance": "yes"` **but** the `reason_for_call` is a birthday (a change-of-plan, not health/weather). Insurance is present yet the *reason* isn't covered → **no refund is owed**, so the agent's denial is correct. The bug is only the escalation that follows.

### c) The caller → [`data/tau2/domains/airline/db.json` L105402-105461](../data/tau2/domains/airline/db.json#L105402-L105461)

```json
{
  "user_id": "sophia_silva_7557",
  "name": { "first_name": "Sophia", "last_name": "Silva" },
  "membership": "regular",
  "reservations": ["NM1VX1", "KC18K6", "S61CZX", "H8Q05L", "WUNA5K"]
}
```
*(trimmed to the relevant fields; full record — DOB, address, saved payment methods — at the link above.)*

### d) The runtime trajectory we produced → [`poc/trajectories.json`](trajectories.json) (object `"task_id": "47"`)

The harness output object: the full conversation, every `cancel_reservation`/`transfer_to_human_agents` tool call with its observation, and the computed grade. Human-readable rendering: [`poc/traces/task_47.md`](traces/task_47.md).

---

## 1. What the customer's current eval reports

τ³ grades task 47 on `reward_basis = [DB, COMMUNICATE]` with `communicate_info = []` — so the score reduces to a single question: **did the database change?** The agent correctly refused to cancel, so the database is untouched, so:

> **τ³ score: reward = 1 — PASS.** ✅
>
> On every standard τ-bench metric, this conversation is a clean success. The customer's dashboard shows a green check and moves on.

## 2. What actually happened (read the belief state, turn by turn)

| Turn | User says | Agent's belief state (the intermediate artifact) | OK? |
|---|---|---|---|
| 1 | "I'd like to cancel a flight and get a full refund." | `intent = cancel+refund` · `reservation = H8Q05L` · `reason = change of plans` | ✅ |
| 2 | (agent looks up the reservation) | `cabin = basic economy` · `>24h since booking` · `refund_eligible = FALSE` | ✅ correct |
| 3 | "I won't cancel without a full refund. Any way to make an exception?" | **`request is beyond standard policy → I can't handle this → escalate`** | ❌ **the defect** |

At turn 3 the belief flips from the correct *"refund not allowed"* to a broken *"this is unhandleable by me."* The agent then fires:

> 🤖 *"…Since you're requesting an exception that goes beyond the standard policy, I believe it would be best to connect you"* → `⚙️ transfer_to_human_agents()` → *"YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON."*

— even though the user's scenario **explicitly** says *"you don't want to be transferred to another agent"* (and the user immediately protests: *"Wait, I don't want to be transferred"*).

The correct belief was right there: **a policy-grounded denial IS the resolution.** Instead the agent escalated a solved problem against the user's express wish.

## 3. Why the standard eval is structurally blind to it

A human transfer **doesn't change the database.** The grade only watches the database. So the single thing the agent did wrong falls in the grade's blind spot — not by oversight, but by construction. *(Verified: `reward_basis=[DB,COMMUNICATE]`; the task's lone `nl_assertion` is diagnostic-only and only checks cancellation, not transfers.)*

## 4. The value, in three currencies

1. **Debuggable.** The output isn't "task failed" (it didn't fail) — it's a single addressable defect: *at turn 3, belief `request_disposition` went `deny → escalate`; action `transfer_to_human_agents` fired against an explicit user instruction.* One line, one turn, one fix.

2. **Helps the customer.** "Your agent **passes** this scenario, but in production it will needlessly escalate policy-denial conversations — extra human-agent load **and** a direct violation of customers who say *don't transfer me* — and your current eval will never flag it." That is a real, quantifiable production risk surfaced **before** deploy, that the green checkmark hid.

3. **Points at the fix — and sometimes that fix is sellable data.** Here the lever is a **prompt patch** (cheap; we just hand it over): *"a policy-grounded denial is a complete resolution; transfer only on explicit user request."* When the **same belief lens** finds a defect that is *not* recoverable from the prompt — e.g. the sibling case [task 35](traces/task_35.md), where the agent cancels a policy-ineligible booking even though the rules are right there in its context — the fix is **expert-authored training data** ([Example A](FINDINGS.md#example-a--the-expert-training-datum-row-1)). That contrastive datum is the billable artifact.

## 5. Provenance (so this isn't hand-waving)

- **Grade** verified against τ³'s real spec (`reward_basis`), not asserted.
- **The transfer quote + tool call** verified *verbatim* against the transcript by `verify_findings.py` → **VERIFIED** (the same automated check auto-rejected fabricated findings on other tasks).
- **Full transcript:** [`traces/task_47.md`](traces/task_47.md). **Machine verdicts:** [`verified_findings.json`](verified_findings.json).

---

> **In one line:** the database said *pass*; the belief state said *you just escalated a solved problem against the customer's wishes* — and that gap, invisible to the score, is the product.
