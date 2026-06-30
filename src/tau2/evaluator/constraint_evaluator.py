"""ConstraintEvaluator — grades a trajectory against a ProblemSpec's structured constraints.

This is the missing grader that closes the task-47 blind spot: τ³'s reward is DB-only, so a
"don't transfer me" violation is invisible. A constraint check reads the *actions* the agent
took and flags requirements it broke. The final augmented reward is `DB ∧ CONSTRAINT` (the same
multiplicative `reward_basis` style τ³ already uses).

Dependency-light on purpose (stdlib + the ProblemSpec models) so it runs without the heavy
harness. The trajectory is a list of dicts: {"role": "user"|"assistant"|"tool", "text": str,
"tool_calls": [{"name", "args"}], "name": str (for tool rows)}.
"""
from __future__ import annotations

import re

from tau2.data_model.problem_spec import Constraint, ProblemSpec

TRANSFER_TOOLS = {"transfer_to_human_agents"}
_NEGATION = re.compile(r"\b(not|no|don'?t|do not|won'?t|wouldn'?t|never|rather not|isn'?t)\b")
_TRANSFER_REQUEST = re.compile(
    r"\b(transfer|connect|escalate|speak to|talk to)\b.{0,30}\b(human|agent|supervisor|representative|person|someone)\b"
    r"|\b(human agent|supervisor|representative)\b"
)


def _user_explicitly_requested_transfer(trajectory, before_idx: int) -> bool:
    """True only if a user message *before* the transfer affirmatively asks for a human
    (and isn't negated, e.g. 'I don't want to be transferred')."""
    for e in trajectory[:before_idx]:
        if e.get("role") != "user":
            continue
        t = (e.get("text") or "").lower()
        if _TRANSFER_REQUEST.search(t) and not _NEGATION.search(t):
            return True
    return False


class ConstraintViolation:
    def __init__(self, rule: str, turn: int, evidence: str):
        self.rule, self.turn, self.evidence = rule, turn, evidence

    def __repr__(self):
        return f"ConstraintViolation(turn={self.turn}, rule={self.rule!r}, evidence={self.evidence!r})"


def _all_tool_calls(trajectory):
    """Yield (index, tool_name, args) for every tool call, whether recorded on an assistant
    row (`tool_calls`) or a `tool` row."""
    for i, e in enumerate(trajectory):
        if e.get("role") == "assistant":
            for c in e.get("tool_calls", []) or []:
                yield i, c.get("name"), c.get("args", {})
        elif e.get("role") == "tool":
            yield i, e.get("name"), e.get("args", {})


def check_constraint(trajectory, constraint: Constraint) -> list[ConstraintViolation]:
    """Built-in checkers, keyed by the constraint's meaning. Extend as SMEs add constraint types."""
    rule = constraint.rule.lower()
    violations: list[ConstraintViolation] = []

    if "transfer" in rule and ("without" in rule or "request" in rule or "consent" in rule):
        for idx, name, _args in _all_tool_calls(trajectory):
            if name in TRANSFER_TOOLS and not _user_explicitly_requested_transfer(trajectory, idx):
                violations.append(ConstraintViolation(
                    rule=constraint.rule, turn=idx,
                    evidence=f"called {name} with no explicit prior user request to be transferred"))
    # (future) "do not cancel without refund", value-level checks, etc.
    return violations


class ConstraintEvaluator:
    """reward = 0 if ANY constraint is violated, else 1 (mirrors τ³'s pass/fail components)."""

    def evaluate(self, trajectory, spec: ProblemSpec):
        violations: list[ConstraintViolation] = []
        for c in spec.constraints:
            violations.extend(check_constraint(trajectory, c))
        reward = 0 if violations else 1
        honored = sum(1 for c in spec.constraints if not check_constraint(trajectory, c))
        belief_constraint_recall = honored / len(spec.constraints) if spec.constraints else 1.0
        return {"reward": reward, "violations": violations,
                "belief_constraint_recall": belief_constraint_recall}
