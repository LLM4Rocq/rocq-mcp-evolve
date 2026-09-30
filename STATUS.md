# STATUS — AI-native Rocq tooling experiment · PHASES 1 & 2 COMPLETE

_Final update: 2026-07-15 · phase 2 (autoformalization + held-out matrix) complete; held-out table archived (REPORT §16)_

## Phase 2 in one paragraph (Jul 9–15)
A self-contained side evaluation asked whether the shipped tools survive
the realistic task (NL spec → multi-file verified dune project) and a
locked held-out split. Autoformalization, strict fair protocol: baseline
10/20 → **evolve 14/20** (pre-registered criterion met; 4-arm replication,
task-clustered p=0.006), sibling rocq-mcp 12/20; at the frontier tier the
unassisted baseline collapses (3/10) while both prover servers double it.
Held-out miniF2F-test, single registered look (six arms, 488 rows each,
integrity-gated): control .66/.28/.23 → rocq-mcp fair .73/.43/.20 →
**evolve .90/.65/.63** pass@1 e/m/h, disjoint 95% CIs vs control in every
bucket, at ~half the cost and latency per solve; a pre-registered
prompt-free pair replicates the gap (.67/.34/.20 vs .93/.61/.69) — the
advantage is the interface, not the prompt. Three verdict-reversing
evaluation artifacts (turn-cap tax, arena censoring, integration racing)
were found, fixed, and documented (REPORT Part II, docs/AUTOFORM.md,
docs/FAILURE_ATLAS_AUTOFORM.md; decision trail A38–A96).

## Phase 1: the run in one paragraph
Starting from a deliberately-naive control, ten measured interface changes
(six kept, four honestly reverted) turned a weak policy's .44/.25/.30 into
.65/.575/.475 (winner_auto2; dev60 pass@1 e/m/h) at −45 % cost — and after two
Fable-driven quality passes (a 43-attempt failure atlas and a 31-finding
adversarial measurement audit) exposed and fixed the defects that made
interfaces look policy-dependent, ONE policy-neutral configuration
(`universal`) is best-or-tied everywhere measured, including **beating the
naive interface in every bucket at the strong policy** (.95/1.00/.85 vs
.925/.95/.80, 2 reps). The held-out protocol number (frozen config, single
mechanically-logged unlock): pass@1 .519/.127/.043 on miniF2F test
(phase-1 mean-over-reps convention; the final six-arm held-out table with
the A78 conventions is in REPORT §16).

## Final deliverables (all in this repo, all pushed)
- **README.md** — describe / install / try-in-2-minutes (verified commands),
  MCP client wiring, real-project usage
- **docs/REPORT.md** — full report: executive summary, every A/B with
  per-bucket numbers, corrected scalability (§5, with retractions), annexes
  (cross-policy, SOTA, teams, in-project context, ssreflect), held-out (§7),
  measurement audit (§7b), threats, conclusions
- **Test suite** — `dune runtest`: 4 suites, 109 checks, all green
  (session contracts + atlas/audit regressions; multi-agent daemon incl.
  merge-renumbering; scalability bounds; gate soundness incl. the
  comment-desync exploit)
- **docs/DESIGN.md** (per-decision rationale) · **docs/FAILURE_ATLAS.md** ·
  **docs/ASSUMPTIONS.md** (A1–A96) · **docs/TASK.md** (original brief)
- **The tool layer**: src/mcp_core, src/session_server (the universal
  surface), src/baseline_server, src/submit_server, src/files_server
  (the multi-agent daemon src/psession was removed in A127; its record
  stays in docs/DESIGN.md); configs/ for every measured condition;
  configs/FROZEN.md
- **Harness**: runner, anti-gaming gate, report/profile/
  monitor/dashboard/plots/sweep, manifests, project_args, repro/setup.sh
  (the team orchestrator harness/run_team.py went with A127)

## Reproduce anything
`./repro/setup.sh <dir>` recreates the pinned environment (Rocq 9.1.1);
`python3 harness/report.py <run_id>` reproduces any table from raw logs;
`python3 harness/dashboard.py` renders the live view; `dune runtest` proves
the shipped binaries honor every measured contract.

## Honest boundaries (details in REPORT §8)
Hard competition problems remain policy-bound (~4-6 % under every design);
universal trails the haiku-tuned config on haiku-hard (.463 vs .475, 4 reps, post-repair A94); the team
pattern is decisively negative at this scale; ssreflect-idiom proving needs
per-project knowledge distillation (roadmap in DESIGN); two measurement
claims were publicly retracted after contamination was found (§5).

## Budget actuals
Policy pool ≈ $250 total across ~6 000 gated attempts · Fable: 2 workflows +
3 implementation agents (~3.7 M subagent tokens) · wall: 6 days incl. two
overnight autonomous pipelines · every number's provenance in logs/ + git.

## Final-day additions (Jul 7, all measured or suite-verified)
- **Fable-tier matrix row**: universal ≥ naive at the strongest policy too
  (.95/1.00/1.00 vs .95/1.00/.95, dev60 1 rep) — policy-neutrality now spans
  three tiers.
- **The mathcomp .07 decomposed**: same tools, fable medium = .93 (either
  context mode) → it was a policy limit, not a tool limit.
- **Counterfactual replay** (272 recorded failures, zero policy cost):
  shipped portfolio already at its closure ceiling; all v3 expansions add
  zero rescues → portfolio unchanged, with corpus-wide evidence.
- **A27 exemplar retrieval**: built, leak-proof, quality-verified — measured
  neutral-to-negative at the weak policy → ships opt-in. Third confirmation
  of the pattern: context without competence doesn't convert.
- **Productization (A28/A29)**: `opam pin` install → `rocq-mcp` binary;
  zero-config MCP registration; runtime `open{file, theorem?}` (Admitted
  rescue, several proofs per session); project load-path auto-discovery
  in-server (no Python in the usage path); completion returns the insertable
  proof script; clean error surfacing. README rewritten (SOTA + all three
  evaluation dimensions in the headline).
- **A30 prefix replay memoization** (user design review): heavy-import
  re-open 14.4 s -> 0.4 s; sibling-file open 0.5 s — imports cost once per
  process. Warm-pool forking across processes = documented next step.
- **CI**: GitHub Actions builds + runs the full suite on push/PR
  (.github/workflows/ci.yml); test PATH resolution made portable.
- **Merged to `main`**; **CI GREEN on both branches** (GitHub Actions:
  full build + 109-check suite on every push, ~12 min warm). Cold-path
  install verified: `opam pin add rocq-mcp-evolve <github-url>` builds and
  installs a working `rocq-mcp` (the uncommitted-opam-file and
  rocq-runtime-9.2-API failures were found and fixed by exactly this test).
- **A31 adversarial product review**: 24 confirmed findings; criticals
  (exemplar leak after `open`) and memoization staleness/truncation fixed
  and repro-verified; discovery/daemon/open majors fixed; 7 minors
  documented as accepted.
- **A32 mathcomp algebra-tactics conditional** (user suggestion): verified
  capability (`by lia` closes ssrnat goals), regime-gated, no benchmark
  lift at the weak policy — the structural-competence boundary confirmed a
  fourth time.
- Test suite: 4 suites, 109 checks, all green.

## Jul 8 hardening (all measured/verified, suite 109 checks green)
- **`build{file}`** (A33): whole-file diagnosis — every broken proof in one
  call via admit-and-continue; pure/stateless.
- **`open` reaches any hole** (A36): earlier broken proofs are Admitted
  automatically — the build->open repair loop works for every hole.
- **Hang safety** (A34/A35, user-reported class): memprof-limits
  allocation-triggered interruption stops vm_compute/native_compute
  divergence (verified on 2016^20214 mod 10: hang -> 5s structured TIMEOUT);
  fork-probe kept as opt-in belt.
- **mathcomp tactic bridge** (A32): zify/algebra-tactics conditional (real
  closing power on boolean-reflection goals; no benchmark lift — structural
  competence remains the weak-policy boundary; ships as depopts).
- **Packaging sweep**: rocq-stdlib + memprof-limits hard deps; mathcomp
  bridges as depopts; only rocq-mcp{,-daemon,-shim} installed (experiment
  servers stay private); module header + tool descriptions refreshed.

## Jul 8 — fair SOTA comparison (A37, user-prompted audit)
The original rocq-mcp comparison was an integration artifact (server still
connecting at agent start in 97-98 % of attempts) — retracted publicly,
fixed with an instant-handshake proxy, rerun 2x/dev60 both policies
(120/120 connected, 0 poisoned). Fair verdict: near accuracy-parity at
sonnet (.95/.925/.80 vs universal .95/1.00/.85), mixed at haiku (rocq-mcp
edges easy; universal +.225 med / +.075 hard); rocq-mcp-evolve' robust edge is
~2x cost-per-solve at sonnet and 20-35 % less wall. "Dominated on all three
axes" was wrong and is corrected everywhere. CI green on both branches.

## Jul 8 evening — dogfood validation (A38)
Fresh-switch install via README verbatim: works. The installed binary,
driven as a raw MCP by a frontier-tier agent, solved 10/10 hard AIME
problems from miniF2F (<=7 calls each, independently recompiled) — an
anecdote, not a benchmark row, but a strong end-to-end validation. Three
small product bugs found and fixed (open null-args, auto_close no-proof
message, standalone candidate.v).

## Needs your input
_(empty — the run is complete)_
