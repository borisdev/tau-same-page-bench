"""Structured ProblemSpec — the refactor proposed in issue #1.

Today a task's requirements live in a free-text `task_instructions` string, so a requirement
like "don't transfer me" is neither gradeable nor diffable against the agent's belief. This
module lifts that string into a structured `ProblemSpec` that serves three masters with zero
drift: it (1) compiles the user-sim prompt, (2) exposes gradeable `constraints`/`invariants`,
and (3) is the typed target the agent's belief state is diffed against.

This module is intentionally dependency-light (pydantic only) so it can be imported and tested
without the rest of the harness. Wiring it into the live user-simulator + evaluator is the next
step on this branch.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Fact(BaseModel):
    slot: str                       # canonical key, e.g. "reservation_id"
    value: str


class Constraint(BaseModel):
    """A requirement the *user* holds the agent to (gradeable, task-scoped)."""
    rule: str                       # e.g. "do not transfer to a human without explicit user request"
    source: Literal["user_stated", "policy", "inferred"] = "user_stated"


class Preference(BaseModel):
    description: str                # soft, non-binding


class Invariant(BaseModel):
    """A domain rule the agent must always obey (SME-authored, cross-task). Used by the grader,
    NOT rendered into the user-sim prompt."""
    rule: str


class ProblemSpec(BaseModel):
    goal: str
    known_facts: list[Fact] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)


def render_prompt(general_instructions: str, spec: ProblemSpec) -> str:
    """Compile a ProblemSpec back into user-simulator prose (the `@property` below).

    Note: `invariants` are deliberately NOT rendered — they are domain rules for the grader,
    not things the simulated user says. The user-sim still reveals facts incrementally at run
    time; this only assembles what it *may* draw on.
    """
    lines = [general_instructions.strip(), "", f"Your goal: {spec.goal}"]
    if spec.known_facts:
        lines.append("What you know: " + "; ".join(f"{f.slot} = {f.value}" for f in spec.known_facts))
    if spec.constraints:
        lines.append("You hold the agent to: " + "; ".join(c.rule for c in spec.constraints))
    if spec.preferences:
        lines.append("Your preferences: " + "; ".join(p.description for p in spec.preferences))
    return "\n".join(lines)


class TaskInstructions(BaseModel):
    """Backward-compatible replacement for the free-text instructions field: `task_instructions`
    stays a string (now *computed*), so existing consumers are unaffected."""
    general_instructions: str
    problem_spec: ProblemSpec

    @property
    def task_instructions(self) -> str:
        return render_prompt(self.general_instructions, self.problem_spec)


# The airline task-47 scenario, lifted into structure. The "no transfer" requirement that was
# buried in prose is now a first-class, gradeable Constraint.
TASK_47_SPEC = TaskInstructions(
    general_instructions=(
        "You are a customer contacting an airline agent. Be persistent and don't provide more "
        "information than necessary. If the agent refuses after you have insisted 5 times, end the call."
    ),
    problem_spec=ProblemSpec(
        goal="Cancel reservation H8Q05L and get a FULL refund (you won't cancel without one).",
        known_facts=[
            Fact(slot="user", value="Sophia Silva (sophia_silva_7557)"),
            Fact(slot="reservation_id", value="H8Q05L"),
            Fact(slot="reason", value="the flight coincides with your best friend's birthday"),
        ],
        constraints=[
            Constraint(rule="do not transfer to a human without explicit user request"),
            Constraint(rule="do not cancel the flight if a full refund is not available"),
        ],
    ),
)
