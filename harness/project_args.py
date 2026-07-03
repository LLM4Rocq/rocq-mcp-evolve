#!/usr/bin/env python3
"""Real-project load-path discovery (A23): given a Rocq project root, emit the
`-Q/-R/-I` arguments that make the session server, baseline server, and gate
resolve the project's OWN modules.

    python3 harness/project_args.py <project_root> [--build] [--json]

Supported layouts, in priority order:
  1. _CoqProject / _RocqProject      — parsed for -Q/-R/-I entries
  2. dune-project                    — scans */dune for (coq.theory (name L))
                                       stanzas; maps each stanza's directory to
                                       its logical name via the _build/default
                                       mirror (where compiled .vo live).
                                       --build runs `dune build` first.

Prints one arg per line (the ROCQ_INIT_ARGS wire format); --json for a list.
Manifest records carry these as "rocq_args"."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def parse_coqproject(f: Path):
    args = []
    toks = []
    for line in f.read_text(errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            toks.extend(line.split())
    i = 0
    root = f.parent
    while i < len(toks):
        t = toks[i]
        if t in ("-Q", "-R") and i + 2 < len(toks) + 1:
            phys = (root / toks[i + 1]).resolve()
            args += [t, str(phys), toks[i + 2]]
            i += 3
        elif t == "-I" and i + 1 < len(toks):
            args += ["-I", str((root / toks[i + 1]).resolve())]
            i += 2
        else:
            i += 1
    return args


THEORY_RE = re.compile(r"\(coq\.theory", re.S)
NAME_RE = re.compile(r"\(name\s+([A-Za-z0-9_.']+)\s*\)")


def parse_dune(root: Path, build: bool):
    if build:
        subprocess.run(["dune", "build"], cwd=root, check=False,
                       capture_output=True, timeout=1800)
    args = []
    for dune in sorted(root.rglob("dune")):
        if "_build" in dune.parts:
            continue
        txt = dune.read_text(errors="replace")
        if not THEORY_RE.search(txt):
            continue
        m = NAME_RE.search(txt)
        if not m:
            continue
        logical = m.group(1)
        rel = dune.parent.relative_to(root)
        mirror = root / "_build" / "default" / rel
        src = mirror if mirror.exists() else dune.parent
        if mirror.exists() or any(dune.parent.glob("*.vo")):
            args += ["-Q", str(src.resolve()), logical]
        else:
            print(f"warning: theory {logical} at {rel} has no compiled mirror "
                  f"(run with --build or `dune build` first)", file=sys.stderr)
            args += ["-Q", str(src.resolve()), logical]
    return args


def project_args(root: Path, build=False):
    for name in ("_CoqProject", "_RocqProject"):
        f = root / name
        if f.exists():
            return parse_coqproject(f)
    if (root / "dune-project").exists():
        return parse_dune(root, build)
    raise SystemExit(f"no _CoqProject/_RocqProject/dune-project under {root}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    args = project_args(Path(a.root).resolve(), a.build)
    if a.json:
        print(json.dumps(args))
    else:
        print("\n".join(args))


if __name__ == "__main__":
    main()
