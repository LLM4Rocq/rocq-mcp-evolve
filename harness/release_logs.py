#!/usr/bin/env python3
"""A149: package the complete campaign logs as ONE zip file for a release of
the private repository, and write the manifest docs/LOGS_RELEASE.md and the
checksum file docs/logs_release.sha256.

    python3 harness/release_logs.py --tag artifact-2026-09-17 --out /path/logs_artifact-2026-09-17.zip
    python3 harness/release_logs.py --tag ... --dry-run          # counts and sizes only

Everything under logs/ goes in, with these exclusions (A149): the CLI
session-file backup directory (logs/cli_sessions_backup/, an audit
input whose conclusion is in the trail), the per-attempt cli_session.jsonl
copies the A142 runner used to make (the effort value they carried is in
each result row), Finder .DS_Store files, and symbolic links (dune install
links inside attempt work dirs; their targets are not part of the record).
Entries are stored as logs/<path> so the zip unpacks in place at the repo
root. Deflate, zip64 (the raw tree exceeds 4 GB). The GitHub release-asset
limit is 2 GiB per file; the script refuses to declare success above it.
"""
import argparse
import hashlib
import os
import sys
import time
import zipfile
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

EXCLUDED_DIRS = {"cli_sessions_backup"}          # top-level under logs/
EXCLUDED_NAMES = {"cli_session.jsonl", ".DS_Store"}
ASSET_LIMIT = 2 * 1024 ** 3


def walk(logs):
    """Yield (path, relpath) for every regular file to ship; count skips."""
    skipped = {"excluded_dir_files": 0, "cli_session": 0, "ds_store": 0, "symlink": 0}
    for root, dirs, files in os.walk(logs, followlinks=False):
        rel_root = Path(root).relative_to(logs)
        if rel_root.parts and rel_root.parts[0] in EXCLUDED_DIRS:
            skipped["excluded_dir_files"] += len(files)
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
        for fn in sorted(files):
            p = Path(root) / fn
            if os.path.islink(p):
                skipped["symlink"] += 1
                continue
            if fn == "cli_session.jsonl":
                skipped["cli_session"] += 1
                continue
            if fn == ".DS_Store":
                skipped["ds_store"] += 1
                continue
            yield p, p.relative_to(logs.parent)
    walk.skipped = skipped


def group_of(rel):
    """Manifest group: logs/runs/<run>, logs/autoform, logs/<other dir>, or
    logs (top-level files)."""
    parts = rel.parts  # ('logs', ...)
    if len(parts) >= 3 and parts[1] == "runs":
        return "/".join(parts[:3])
    if len(parts) >= 2 and (Path(*parts[:2]).suffix == "" and len(parts) > 2):
        return "/".join(parts[:2])
    return "logs"


def fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", type=Path, help="zip path to write (required unless --dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--repo", default="LLM4Rocq/rocq-mcp-evolve-private")
    args = ap.parse_args()
    if not args.dry_run and not args.out:
        sys.exit("--out is required unless --dry-run")
    logs = common.LOGS
    groups = OrderedDict()
    total_files = total_bytes = 0
    files = list(walk(logs))
    for p, rel in files:
        g = groups.setdefault(group_of(rel), {"files": 0, "bytes": 0})
        sz = p.stat().st_size
        g["files"] += 1
        g["bytes"] += sz
        total_files += 1
        total_bytes += sz
    skipped = walk.skipped
    print(f"{total_files} files, {fmt_bytes(total_bytes)} raw, in {len(groups)} groups; skipped {skipped}", flush=True)
    if args.dry_run:
        for g, v in groups.items():
            print(f"  {g:60s} {v['files']:7d} {fmt_bytes(v['bytes']):>10s}")
        return

    t0 = time.time()
    with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zf:
        for i, (p, rel) in enumerate(files):
            zf.write(p, str(rel))
            if i % 20000 == 0 and i:
                print(f"  {i}/{total_files} files, {time.time() - t0:.0f}s", flush=True)
    size = args.out.stat().st_size
    h = hashlib.sha256()
    with open(args.out, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    digest = h.hexdigest()
    print(f"wrote {args.out}: {fmt_bytes(size)}, sha256 {digest}, {time.time() - t0:.0f}s", flush=True)
    if size > ASSET_LIMIT:
        sys.exit(f"!! {fmt_bytes(size)} exceeds the 2 GiB release-asset limit; not publishable as one file")

    docs = common.REPO / "docs"
    (docs / "logs_release.sha256").write_text(f"{digest}  {args.out.name}\n")
    lines = [
        "# Complete logs: release asset of the private repository",
        "",
        f"The untracked `logs/` tree ({fmt_bytes(total_bytes)} on disk, {total_files:,} regular files) is published as ONE",
        f"zip file, `{args.out.name}` ({fmt_bytes(size)}, sha256 `{digest}`), attached to release",
        f"`{args.tag}` of `git@github.com:{args.repo}.git`, whose tag points at the commit that carries this",
        "manifest. Entries are stored as `logs/...`, so the archive unpacks in place at the repository root;",
        "`python3 harness/results_all_gen.py --check` then reproduces `docs/RESULTS_ALL.md` from it.",
        "",
        "Not shipped (A149): the CLI session-file backup directory (`logs/cli_sessions_backup/`, an audit input",
        "whose conclusion is recorded in docs/ASSUMPTIONS.md A142), the per-attempt `cli_session.jsonl` copies",
        f"({skipped['cli_session']:,} files; the effort value each carried is in its result row, `effort_recorded`, or in",
        "the run's `effort_recovered.jsonl`), `.DS_Store` files, and symbolic links inside attempt work",
        f"directories ({skipped['symlink']}).",
        "",
        "## Fetch, verify, restore",
        "",
        "```sh",
        f"gh release download {args.tag} --repo {args.repo} --pattern '{args.out.name}' --dir /tmp/logs_release",
        f"(cd /tmp/logs_release && shasum -a 256 -c \"$OLDPWD/docs/logs_release.sha256\")",
        f"unzip -q /tmp/logs_release/{args.out.name} -d .      # from the repository root; creates ./logs/",
        "python3 harness/results_all_gen.py --check",
        "```",
        "",
        "## Contents",
        "",
        "| group | files | raw |",
        "|---|---:|---:|",
    ]
    for g, v in groups.items():
        lines.append(f"| `{g}` | {v['files']:,} | {fmt_bytes(v['bytes'])} |")
    lines.append(f"| **total** | **{total_files:,}** | **{fmt_bytes(total_bytes)}** |")
    lines.append("")
    lines.append(f"Generated by `harness/release_logs.py` on {time.strftime('%Y-%m-%d')}.")
    (docs / "LOGS_RELEASE.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {docs / 'LOGS_RELEASE.md'} and {docs / 'logs_release.sha256'}")


if __name__ == "__main__":
    main()
