#!/usr/bin/env python3
"""Count multi-tool-call assistant turns (the turn==call claim's artifact).

    python3 harness/count_parallel_calls.py logs/autoform/af2_base logs/autoform/af2_evolve

Prints, per run: assistant messages, tool-bearing messages, and messages
carrying MORE than one tool_use block (the 'parallel calls' count)."""
import glob, json, sys

for d in sys.argv[1:]:
    msgs = toolmsgs = multi = 0
    for tp in glob.glob(f"{d}/attempts/*/transcript.jsonl"):
        for l in open(tp, errors="replace"):
            if '"assistant"' not in l:
                continue
            try:
                e = json.loads(l)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "assistant":
                continue
            msgs += 1
            k = sum(1 for b in e.get("message", {}).get("content", [])
                    if isinstance(b, dict) and b.get("type") == "tool_use")
            toolmsgs += (k > 0)
            multi += (k > 1)
    print(f"{d}: assistant_msgs={msgs} tool_bearing={toolmsgs} multi_call={multi}")
