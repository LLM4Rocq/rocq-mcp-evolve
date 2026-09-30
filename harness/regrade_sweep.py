#!/usr/bin/env python3
"""A75 regrade sweep: re-run the FIXED gate on every attempt whose workspace
contains more than one coq.theory dune (the deterministic trigger class for
the vo[0].parent bug). Originals stay untouched; changed rows land in
<run>/regrades.jsonl (the dashboard applies them as overrides)."""
import json, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import common, autoform_gate
from run_autoform import layer_rank

# A63 policy: gate build budget 1800s; exceeding it = build_failed
_orig_run = autoform_gate.run
autoform_gate.run = lambda cmd, cwd=None, timeout=600: _orig_run(cmd, cwd=cwd, timeout=1800)

LOGS = common.LOGS / "autoform"
runs = sorted(p for p in LOGS.iterdir() if (p / "results.jsonl").exists())
n_scan = n_hit = n_flip = 0
for run in runs:
    rows = {(r["task"], r["rep"]): r for r in common.read_jsonl(run / "results.jsonl")}
    regrades = []
    for adir in sorted((run / "attempts").iterdir()) if (run / "attempts").exists() else []:
        ws = adir / "workspace"
        if not ws.exists():
            continue
        n_scan += 1
        theories = []
        for dune in ws.rglob("dune"):
            if "_build" in dune.parts:
                continue
            try:
                if "coq.theory" in dune.read_text(errors="replace"):
                    theories.append(dune)
            except OSError:
                pass
        if len(theories) < 2:
            continue
        n_hit += 1
        task = adir.name.rsplit("__rep", 1)[0]
        rep = int(adir.name.rsplit("__rep", 1)[1])
        tkey = task[3:] if task.startswith("w2_") else task
        tdir = common.REPO / "data" / "autoform" / tkey
        if not tdir.exists():
            continue
        old = rows.get((task, rep), {})
        done = {(r["task"], r["rep"]) for r in common.read_jsonl(run / "regrades.jsonl")}
        if (task, rep) in done:
            continue
        try:
            v = autoform_gate.check(tdir, ws)
        except subprocess.TimeoutExpired:
            v = {"solved": False, "reason": "build_failed",
                 "layers": {"build": "gate build exceeded 1800s (A63 policy)"}}
        if v.get("reason") == old.get("reason"):
            continue
        n_flip += 1
        print(f"  FLIP {run.name}/{adir.name}: {old.get('reason')} -> {v.get('reason')}")
        newrow = dict(old)
        newrow.update({"solved": v["solved"], "reason": v.get("reason"),
                       "layer": layer_rank(v), "n_probes": v.get("n_probes"),
                       "regraded": "A75 gate fix", "ts": time.time()})
        regrades.append(newrow)
    if regrades:
        with open(run / "regrades.jsonl", "a") as f:
            for r in regrades:
                f.write(json.dumps(r) + "\n")
print(f"scanned {n_scan} attempts, {n_hit} in trigger class, {n_flip} verdicts changed")
