#!/usr/bin/env python3
"""Scalability sweep: run a fixed stratified batch at N ∈ {1,2,4,8,...}
parallel agents and measure throughput + resource use per N.

    python3 harness/sweep.py --config session --ns 1,2,4,8

Per N: makespan, attempts/hour, per-bucket success, per-call latency p50/p95
(server logs), sampled peak/mean RSS and CPU% of the whole process tree
(claude CLI + MCP servers + prover workers), all written to
logs/runs/sweep_<config>_N<k>/ + a summary jsonl.

Methodology notes: resources are sampled every 2 s by matching the process
command lines this harness spawns (claude -p, rocq_agent_*, rocqworker,
rocq compile); the machine must be otherwise quiet. The problem batch is
fixed (first 8 per bucket of dev60) so the difficulty mix is identical at
every N.
"""

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common

PROC_RE = re.compile(r"claude -p|rocq_agent_|rocqworker|rocq compile")


def make_batch(per_bucket=8):
    recs = common.load_manifest("dev60")
    out, seen = [], {}
    for r in recs:
        b = r["difficulty"]
        if seen.get(b, 0) < per_bucket:
            out.append(r)
            seen[b] = seen.get(b, 0) + 1
    p = common.MANIFESTS / "sweep24.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in out))
    return p, len(out)


class Sampler(threading.Thread):
    def __init__(self, out_path):
        super().__init__(daemon=True)
        self.out_path = out_path
        self.stop_ev = threading.Event()
        self.peak_rss = 0
        self.samples = []

    def run(self):
        while not self.stop_ev.wait(2.0):
            try:
                out = subprocess.run(
                    ["ps", "-axo", "rss,pcpu,command"], capture_output=True, text=True
                ).stdout
            except OSError:
                continue
            rss_kb, cpu = 0, 0.0
            for line in out.splitlines():
                if PROC_RE.search(line):
                    parts = line.split(None, 2)
                    try:
                        rss_kb += int(parts[0])
                        cpu += float(parts[1])
                    except (ValueError, IndexError):
                        pass
            self.peak_rss = max(self.peak_rss, rss_kb)
            self.samples.append({"ts": time.time(), "rss_kb": rss_kb, "pcpu": cpu})
        Path(self.out_path).write_text(
            "".join(json.dumps(s) + "\n" for s in self.samples)
        )

    def stop(self):
        self.stop_ev.set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ns", default="1,2,4,8")
    ap.add_argument("--per-bucket", type=int, default=8)
    args = ap.parse_args()

    batch, n_problems = make_batch(args.per_bucket)
    summary_path = common.LOGS / f"sweep_{args.config}_summary.jsonl"
    for n in [int(x) for x in args.ns.split(",")]:
        run_id = f"sweep_{args.config}_N{n}"
        run_dir = common.LOGS / "runs" / run_id
        if (run_dir / "results.jsonl").exists() and len(
            common.read_jsonl(run_dir / "results.jsonl")
        ) >= n_problems:
            print(f"[sweep] N={n} already complete, skipping")
            continue
        print(f"[sweep] N={n} starting ({n_problems} attempts)")
        sampler = Sampler(run_dir / "resources.jsonl")
        run_dir.mkdir(parents=True, exist_ok=True)
        sampler.start()
        t0 = time.time()
        subprocess.run(
            [sys.executable, str(Path(__file__).parent / "run_eval.py"),
             "--config", args.config, "--manifest", str(batch),
             "--reps", "1", "--parallel", str(n), "--run-id", run_id],
            check=False,
        )
        makespan = time.time() - t0
        sampler.stop()
        sampler.join(timeout=10)
        rows = common.read_jsonl(run_dir / "results.jsonl")
        resumed = 0
        meta_p = run_dir / "run_meta.json"
        if meta_p.exists():
            try:
                resumed = json.loads(meta_p.read_text()).get("resumed_skipping", 0)
            except json.JSONDecodeError:
                pass
        cpu_mean = (
            sum(s["pcpu"] for s in sampler.samples) / max(len(sampler.samples), 1)
        )
        rec = {
            "config": args.config,
            "N": n,
            "attempts": len(rows),
            "solved": sum(1 for r in rows if r.get("solved")),
            "makespan_s": round(makespan, 1),
            "attempts_per_hour": (round(3600 * len(rows) / makespan, 1)
                                  if not resumed else None),
            "resumed_attempts_skipped": resumed,
            "peak_rss_mb": round(sampler.peak_rss / 1024, 1),
            "cpu_pct_mean": round(cpu_mean, 1),
            "wall_s_mean": round(
                sum(r.get("wall_s") or 0 for r in rows) / max(len(rows), 1), 1
            ),
            "ts": time.time(),
        }
        common.append_jsonl(summary_path, rec)
        print(f"[sweep] N={n}: {json.dumps(rec)}")


if __name__ == "__main__":
    main()
