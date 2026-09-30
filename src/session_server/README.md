# rocq-tools session server (rocq-mcp-evolve)

An MCP server exposing a live Rocq (Coq/Rocq 9.1) prover for developing and
verifying proofs in a project. All file paths may be workspace-relative
(resolved against `ROCQ_PROJECT_ROOT`, else the server's cwd). Project load
paths are auto-discovered from the dune project — build the project first so
imports resolve.

## Tools

| tool | what it does |
|---|---|
| `open {file, theorem?}` | Open a `.v` file and start an interactive session on a theorem (default: the first unproven one). Returns the goal. Re-opening a file replays unchanged leading text from cache, so warm re-opens are fast. |
| `build {file}` | Diagnose a whole `.v` file in one call: compiles it and reports EVERY broken proof with its error and goal state, not just the first. |
| `check {script}` | Check a complete proof attempt in one call: pass the entire script (from after `Proof.` to `Qed.`). On failure it commits the longest valid prefix and reports the first failing step with the goal there, so you can repair from where it broke. |
| `step {text}` | Execute one or more sentences (tactics) in the live session; shows the resulting goals. |
| `try {candidates}` | Try up to 8 candidate tactic scripts speculatively against the current state, in order; the first that fully succeeds is committed, the rest are reported with their failure points. |
| `auto_close {}` | Run the standard finishing portfolio against the current goal in one call (lia, lra, nra, nia, field, ring variants, auto — plus synthesized hint terms). Call it first on every goal before doing structural work. If the session preloaded tactic modules your file does not import, the completion message tells you which `Require` lines to add. |
| `state {}` | Show all open goals and the committed proof so far. |
| `rollback {n}` | Undo the last N committed sentences and show the goal state you are back to. |
| `verify {}` | Verify the whole project before declaring it done: clean `dune build` at the project root plus a scan of every `.v` file for admit/Admitted/Axiom and friends. Returns ok or the exact failures. |

## Typical workflow

Write definitions and theorem statements to files and get the project
building; then for each unproven theorem: `open` it, throw `auto_close` at
the goal, drive what remains with `step`/`try`/`check`, and paste the
returned finished script back into the file. `build {file}` reports every
broken proof in a file at once; `verify {}` is the final pre-done check.
On proof completion the server returns the full script to paste, plus any
`Require` lines the file is missing for tactics the session preloaded.
