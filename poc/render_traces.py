"""Render each trajectory to a readable, linkable markdown transcript with turn numbers,
so the failure-pattern table can point at the exact granular moment (observability)."""
import os, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(ROOT, "poc/traces"), exist_ok=True)
TRAJ = json.load(open(os.path.join(ROOT, "poc/trajectories.json")))

for t in TRAJ:
    tid = t["task_id"]
    grade = "✅ PASS" if t["reward"] else "❌ FAIL"
    lines = [f"# Trace — airline task {tid}  ({grade}, db_changed={t['db_changed']})", "",
             f"**Scenario (hidden from agent):** {t['instructions']}", "",
             f"**Purpose (ground truth):** {t['purpose']}", "", "---", ""]
    turn = 0
    for e in t["trajectory"]:
        if e["role"] == "user":
            turn += 1
            lines.append(f"**[turn {turn}] 🧑 user:** {e['text']}\n")
        elif e["role"] == "assistant" and (e.get("text") or e.get("tool_calls")):
            if e.get("text"):
                lines.append(f"**[turn {turn}] 🤖 agent:** {e['text']}\n")
            for c in e.get("tool_calls", []):
                lines.append(f"> ⚙️ `call {c['name']}({json.dumps(c['args'])})`\n")
        elif e["role"] == "tool":
            obs = e["observation"].replace("\n", " ")[:240]
            lines.append(f"> 📦 `{e['name']}` → {obs}\n")
    open(os.path.join(ROOT, f"poc/traces/task_{tid}.md"), "w").write("\n".join(lines))
    print(f"task_{tid}.md  ({grade})")
