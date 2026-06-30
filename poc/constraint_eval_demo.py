"""Demo for issue #1: lift task 47's "no transfer" requirement into a structured Constraint,
grade it with ConstraintEvaluator, and watch the verdict flip PASS -> FAIL — the violation the
DB-only grade is structurally blind to.

Run:  <venv>/bin/python poc/constraint_eval_demo.py
"""
import sys, types, os, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for name, sub in [("tau2", "src/tau2"), ("tau2.data_model", "src/tau2/data_model"),
                  ("tau2.evaluator", "src/tau2/evaluator")]:
    m = types.ModuleType(name); m.__path__ = [os.path.join(ROOT, sub)]; m.__package__ = name
    sys.modules[name] = m

from tau2.data_model.problem_spec import TASK_47_SPEC, render_prompt
from tau2.evaluator.constraint_evaluator import ConstraintEvaluator

# task 47's trajectory + its already-verified DB grade (from the PoC pipeline)
TRAJ = {t["task_id"]: t for t in json.load(open(os.path.join(ROOT, "poc/trajectories.json")))}["47"]
DB_GRADE = {f["task_id"]: f for f in json.load(open(os.path.join(ROOT, "poc/verified_findings.json")))}["47"]["recomputed_grade"]

spec = TASK_47_SPEC.problem_spec
res = ConstraintEvaluator().evaluate(TRAJ["trajectory"], spec)
db, con = DB_GRADE, res["reward"]
combined = db * con  # τ³-style multiplicative reward_basis

print("=" * 64)
print("  Structured ProblemSpec — the user-sim prompt, COMPILED from slots")
print("=" * 64)
print(render_prompt(TASK_47_SPEC.general_instructions, spec))
print("\n  constraints (now first-class, gradeable):")
for c in spec.constraints:
    print(f"    • {c.rule}")

print("\n" + "=" * 64)
print("  Augmented grading of task 47")
print("=" * 64)
print(f"  DB grade (τ³ today) ............. {'PASS' if db else 'FAIL'}   (reward={db}; DB unchanged)")
print(f"  Constraint grade (NEW) ......... {'PASS' if con else 'FAIL'}   (reward={con})")
for v in res["violations"]:
    print(f"      ↳ VIOLATED @ turn {v.turn}: {v.rule}")
    print(f"        evidence: {v.evidence}")
print(f"  Combined (DB ∧ CONSTRAINT) ..... {'PASS' if combined else 'FAIL'}")
print(f"\n  → τ³ scored this PASS. With one structured constraint, the grade flips to "
      f"{'FAIL' if not combined else 'PASS'}.")

print("\n" + "=" * 64)
print("  Belief-vs-spec diff")
print("=" * 64)
print(f"  spec constraints: {len(spec.constraints)}   honored by agent: "
      f"{int(res['belief_constraint_recall'] * len(spec.constraints))}   "
      f"→ belief constraint-recall = {res['belief_constraint_recall']:.2f}")
for rule in dict.fromkeys(v.rule for v in res["violations"]):
    print(f"  missed slot: constraint:\"{rule}\"")
