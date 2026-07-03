#!/usr/bin/env python3
"""In-project proving benchmark (A20): extract mid-file lemmas from the local
Rocq stdlib checkout, strip their proofs, and emit tasks whose immutable
prefix is the ENTIRE file above the lemma statement.

    python3 harness/make_inproject_manifest.py

Verification: every sampled task's prefix + 'Admitted.' must compile against
the INSTALLED stdlib (the checkout may drift from the installed version;
incompatible extractions are filtered out automatically). Difficulty =
ground-truth proof length in sentences: short 1-3, medium 4-10, long >10.
"""

import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
from gate import ENV_INJECT

# (root, subdirs, source tag, output manifest)
PROJECTS = {
    "stdlib": (Path("/Users/gbaudart/Project/llm4rocq/rocq-stdlib/theories"),
               ["Reals", "Arith", "ZArith", "NArith", "Lists"],
               "stdlib_project", "inproject60.jsonl"),
    "mathcomp": (Path("/Users/gbaudart/Project/llm4rocq/math-comp"),
                 ["boot", "order"],
                 "mathcomp_project", "mathcomp60.jsonl"),
}
PER_BUCKET = 20
MIN_PREFIX_LINES = 80  # mid-file: real context above the target

STMT_RE = re.compile(
    r"^(Lemma|Theorem|Fact|Corollary|Proposition)\s+([A-Za-z_][A-Za-z0-9_']*)",
    re.MULTILINE,
)


def sentences(text):
    return len(re.findall(r"\.(?=\s|$)", text))


def extract_tasks(vfile: Path, source_tag="stdlib_project"):
    src = vfile.read_text(errors="replace")
    out = []
    for m in STMT_RE.finditer(src):
        name = m.group(2)
        # end of the statement sentence
        stmt_end = re.compile(r"\.(?=\s|$)").search(src, m.end())
        if not stmt_end:
            continue
        after = src[stmt_end.end():]
        pm = re.match(r"\s*Proof(\s+(using[^.]*)?)?\.", after)
        if not pm:
            continue
        qm = re.search(r"\b(Qed|Defined)\s*\.", after)
        if not qm:
            continue
        proof_body = after[pm.end():qm.start()]
        if "Admitted" in proof_body or "Abort" in proof_body:
            continue
        prefix = src[: stmt_end.end()]
        if prefix.count("\n") < MIN_PREFIX_LINES:
            continue
        n = sentences(proof_body)
        bucket = "short" if n <= 3 else "medium" if n <= 10 else "long"
        stmt_text = src[m.start(): stmt_end.end()]
        out.append({
            "problem_id": f"{vfile.stem}__{name}",
            "source": source_tag,
            "difficulty": bucket,
            "theorem_name": name,
            "path": str(vfile),
            "prefix_chars": stmt_end.end(),
            "prefix_lines": prefix.count("\n"),
            "statement": stmt_text,
            "gt_proof_sentences": n,
        })
    return out


def verify(task) -> bool:
    src = Path(task["path"]).read_text(errors="replace")[: task["prefix_chars"]]
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "t.v"
        p.write_text(src + "\nAdmitted.\n")
        try:
            r = subprocess.run(["rocq", "compile", *ENV_INJECT, "t.v"], cwd=td,
                               env=None, capture_output=True, timeout=120)
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            return False


def main():
    import sys as _sys
    proj = _sys.argv[1] if len(_sys.argv) > 1 else "stdlib"
    checkout, dirs, tag, outname = PROJECTS[proj]
    pool = []
    for d in dirs:
        for vf in sorted((checkout / d).rglob("*.v")):
            pool.extend(extract_tasks(vf, tag))
    rng = random.Random(42)
    by_bucket = {}
    for t in sorted(pool, key=lambda t: t["problem_id"]):
        by_bucket.setdefault(t["difficulty"], []).append(t)
    print({b: len(v) for b, v in by_bucket.items()})
    chosen = []
    for b, cands in by_bucket.items():
        rng.shuffle(cands)
        kept = []
        for t in cands:
            if len(kept) >= PER_BUCKET:
                break
            if verify(t):
                kept.append(t)
            # else silently skip: checkout/installed drift or context deps
        print(f"{b}: kept {len(kept)} (scanned {cands.index(t)+1 if cands else 0})")
        chosen.extend(kept)
    out = common.MANIFESTS / outname
    out.write_text("".join(json.dumps(t) + "\n" for t in chosen))
    print(f"wrote {len(chosen)} tasks to {out}")
    lens = [t["prefix_lines"] for t in chosen]
    if lens:
        print(f"prefix lines: min {min(lens)}, median {sorted(lens)[len(lens)//2]}, max {max(lens)}")


if __name__ == "__main__":
    main()
