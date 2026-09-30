<!-- Frozen excerpt of the sibling rocq-mcp server's README (its Tools and
     Recommended-usage sections, verbatim; operator/deployment sections
     excluded per the A60 documentation rule — same rule applied to both
     servers). Source: ../rocq-mcp/README.md -->

# rocq-mcp

## Tools

The server exposes eleven MCP tools:

### Compilation tools (coqc-based, no pytanque needed)

| Tool | Description |
|------|-------------|
| **`rocq_compile`** | Batch-compile Rocq source code via coqc. Best for checking a finished proof. On error, returns error positions and a `state_capture_status` field; when `pet`/coq-lsp is available and the failure is inside a proof, also returns a reusable `state_id` and the goals at the error position. For scratch iteration, prefer `rocq_start` + `rocq_check` / `rocq_step_multi` (interactive session keeps imports warm). |
| **`rocq_compile_file`** | Whole-file `coqc` compile of a `.v` file on disk. Best for finished proofs, axiom audits, and final verification. Preferred over `rocq_compile` for large files (source stays on disk, no full-text transmission over MCP). On error, returns error positions and a `state_capture_status` field; when `pet`/coq-lsp is available and the failure is inside a proof, also returns a reusable `state_id` and the goals at the error position. Cleans up compilation artifacts but preserves the source file. Three opt-in tuning kwargs (`keep_vo`, `mode`, `timing`) — see the **Compile-file options** callout below. For scratch iteration, prefer `rocq_start` + `rocq_check` / `rocq_step_multi` (interactive session keeps imports warm). On failure with `pet` available, the response also carries an `errors` list with per-declaration entries — see the Multi-error reporting callout below. |
| **`rocq_verify`** | Verify that a proof actually proves the original statement. Wraps in a `Module M.` sandbox to catch type redefinition, `Admitted`/`Abort`, custom axioms, and statement mismatches. Run after `rocq_compile` or `rocq_compile_file` succeeds. |

### Interactive tools (pytanque-based, require `pet`)

| Tool | Description |
|------|-------------|
| **`rocq_query`** | Search the Rocq environment — find lemmas, check types, inspect definitions. Three context modes: **preamble** (import commands as a string), **file** (a `.v` file path whose definitions are in scope), or **from_state** (a live `state_id` from a `rocq_check` session — the query sees opened scopes, hypotheses, and local definitions). Use `from_state=<state_id>` to introspect mid-proof without re-specifying preamble. Optional `max_results` parameter limits output for broad searches. Does not modify any proof state. |
| **`rocq_assumptions`** | List the axioms a theorem depends on. Takes a required `file` parameter (path to the `.v` file where the theorem is defined) to set up the full environment. Returns `assumptions: list[str]` of `"name : type"` pairs from `Print Assumptions` (empty when the theorem is closed under the global context) plus the full `raw_output` for agents that want it. No classification — `rocq_assumptions` is pure introspection; the agent decides what's safe to trust. Use `rocq_verify` for a sandboxed admit-free / axiom-policy decision on a candidate proof. |
| **`rocq_start`** | Start an interactive proof session and return proof goals. Three modes: (1) by theorem name, (2) by position — jump to any point in a file to inspect proof goals there (e.g., error positions from `rocq_compile`); cursor rounds forward through the sentence containing it, so a cursor anywhere on a sentence (including its period) yields the state **after** that sentence, and whitespace before a sentence yields the state **before** it (see docstring for the full rule), (3) from imports. Returns a `state_id` for use with `rocq_check` and `rocq_step_multi`. Optional `force_restart=True` kills pet and clears the state table — recovery primitive for accumulated RAM bloat, indexing corruption, or a state expiry that repeats after a plain retry (see Concurrency model). |
| **`rocq_check`** | Run proof commands with cached imports — fast iterative checking. **Requires `from_state`** (the `state_id` returned by `rocq_start` or a previous `rocq_check`). On error, returns `last_valid_state_id` for immediate recovery via `rocq_check(from_state=...)` or `rocq_step_multi(from_state=...)`. Includes `stale_warning` if the source file was modified since session start. |
| **`rocq_step_multi`** | Try multiple tactics at once — find what works without guessing. **Requires `from_state`**. Useful for auto-solving subgoals (pass standard automation tactics) or exploring proof structure. Does not advance the state; commit the winner with `rocq_check`. Max 20 tactics per call. |
| **`rocq_toc`** | Get the structure of a `.v` file: all definitions, lemmas, theorems, and sections as a hierarchical outline. Does not require an active session. |
| **`rocq_notations`** | List all notations in a Rocq statement and how they resolve (which scope, which module). Helps debug notation ambiguity (e.g., is `+` in `nat_scope` or `Z_scope`?). |

### Diagnostic tools

| Tool | Description |
|------|-------------|
| **`rocq_diag`** | Operational diagnostics: pet health, memory headroom, system load average, recent errors, currently-live proof states. Use after `pet_restarted: True` to diagnose what happened, before a long `vm_compute` to check memory headroom, or **as an orchestrator's monitoring primitive** — call it between sub-agent dispatches to spot shared-pet contention (`live_states[*].file` shows entries from peer callers), accumulating RAM bloat, or a pile-up in `recent_errors`. Does not spawn pet if it is not running; safe to call without `pet` installed. |

> **Stale file warning:** Interactive sessions (`rocq_start` / `rocq_check` / `rocq_step_multi`) read the `.v` file at session start and do not track subsequent edits. If another process or agent modifies the file while a session is active, the proof state becomes stale and tactics may fail or produce wrong results. In multi-agent setups, **work on a copy of the file** for interactive proving, or restart the session with `rocq_start` after edits. A `stale_warning` field is returned when a file modification is detected. See also the [Concurrency model](#concurrency-model) section below.

> **Workspace auto-detection:** When a file-accepting tool (`rocq_compile_file`, `rocq_query`, `rocq_assumptions`, `rocq_toc`, `rocq_start`) is called without an explicit `workspace`, the server walks up from the file's directory looking for `_RocqProject`, `_CoqProject`, or `dune-project` markers and uses the directory of the innermost match. Falls back to `ROCQ_WORKSPACE` if no marker is found. Pass `workspace=` explicitly to override (e.g. for monorepos with nested project files).

> **Workspace warning:** When the resolved workspace contains no `_RocqProject` / `_CoqProject` / `dune-project` marker AND the call provided explicit `workspace=` or a `file=` hint, the response carries `workspace_warning: str` advising on the load-path resolution. Source-string tools without `workspace=` / `file=` (the legitimate scratch / one-off workflow) stay quiet.

> **.vo rebuild warning:** When `rocq_compile_file` rewrites `.vo` artifacts in a workspace that has one or more active interactive sessions (`rocq_start` / `rocq_check` / `rocq_step_multi`), the response carries `vo_rebuild_warning: str` advising the other agents to call `rocq_start` again to refresh held dependency state. Quiet when no `.vo` changed, when no interactive session lives in this workspace, or when the workspace exceeds the internal scan cap. *Calling `rocq_compile_file` with `keep_vo=True` makes the `.vo` persist between calls, so subsequent compiles of the same file are more likely to trip this warning.*

> **Multi-error reporting:** When `rocq_compile_file` fails (`reason: "compile_error"`) and `pet` is available, the response carries `errors: list[dict]` with per-declaration entries (`proof_name`, `kind`, `start_line`, `end_line`, `code`, `message`) covering errors in named declarations and top-level vernaculars (broken `Require`, broken `Notation`, etc.) reached via inter-chunk regions. This surfaces additional errors beyond the first one coqc reports; cascade failures within a single proof body are deduplicated. Collection stops at `ROCQ_COMPILE_MULTI_ERROR_CAP` (default 20; set to `0` to disable). The field can be present and **empty** (`errors: []`) when the walker ran but pet did not reproduce the coqc-reported failure — treat it as "no additional errors found" rather than "no errors at all." Quiet on successful compiles, when `pet` is unavailable, and on source-string `rocq_compile` (this feature is `rocq_compile_file` only).

> **Compile-file options:** `rocq_compile_file` accepts three opt-in tuning kwargs. All default off — pure additions, no behavior change to the baseline call.
>
> - **`keep_vo=True`** preserves the produced `.vo`/`.vok`/`.vos` artifacts. Useful when a sibling file `Require`s the result; the default behavior is to clean every artifact except the source `.v`. *Combining `keep_vo=True` with `mode="vos"` produces only a `.vos`* — downstream full-mode `Require Import` will then fail with `"Unable to locate library ... (.vos file)"`. Use `keep_vo=True` with `mode="full"` when the sibling consumer expects a `.vo`.
> - **`mode="vos"`** selects a fast statements-only pre-pass (`coqc -vos`). Skips proof bodies *entirely* — does NOT execute them — so it catches missing imports, statement type errors, holes, and notation conflicts in seconds, but accepts any proof body (`Theorem t : False. Proof. exact I. Qed.` passes under `"vos"`). Use as a cheap pre-pass during iteration, then run `mode="full"` for the real check.
> - **`timing=True`** runs coqc with `-time` and adds a `timing: {total_sentences, top_slowest, last_completed}` response field carrying per-sentence diagnostics; `top_slowest` is capped at 5 by descending duration. On timeout, `last_completed` is woven into the error string: `"timed out after 590s. Last completed sentence: line 221 [Theorem.foo] (15.3s)"`. On a successful compile, `last_completed` is the file's literal final sentence (not a failure marker).

> **Proof-tactics chain status:** When a `rocq_check` call finishes a proof (`proof_finished: True`), the server walks the LRU state table backward from the leaf to reconstruct `proof_tactics`. If an ancestor state was LRU-evicted, or (defensively) a cycle is detected, the walk cannot complete; the response then **omits** `proof_tactics` and `proof_hint` and carries `proof_tactics_status` (`"ancestor_evicted"` or `"cycle"`), `proof_tactics_broken_at: int` (the state id where the walk gave up), and a short `proof_tactics_hint` instead. Clients that ignore these keys see no half-chain — they never render a partial walk as a finished proof.

> **Per-call timeout clamp:** When any pet-routed tool (`rocq_query`, `rocq_start`, `rocq_step_multi`, `rocq_check`, `rocq_assumptions`, `rocq_toc`, `rocq_notations`) is invoked with `timeout=<seconds>` exceeding `ROCQ_QUERY_TIMEOUT_CAP` (default 300), the call runs with the cap as the actual budget and the response carries `clamped_timeout: <cap>`. The `timeout=` parameter is the user's request; `clamped_timeout` is the server-side ceiling.

### Choosing a tool

The tools table above is reference-style.  This subsection is intent → tool: find the row that matches what you want to do, then read its tool's full entry above for details.

| If you want to... | Use |
|---|---|
| Iteratively develop a single proof, trying tactics | `rocq_start` + `rocq_check` / `rocq_step_multi` |
| Inspect proof state at a specific line / character | `rocq_start(file=..., line=..., character=...)` — cursor rounds forward through its sentence; point at whitespace **before** a sentence for state-before |
| Search for a lemma by pattern (e.g. `Search _.`) | `rocq_query` |
| Compile a finished `.v` file (whole-file check, axiom audit) | `rocq_compile_file` |
| Compile a finished proof from a string buffer | `rocq_compile` |
| **Probe a scratch file in `/tmp`** | `rocq_start(file='/tmp/probe.v', theorem=...)` — **never `coqc /tmp/probe.v`** (coqc reloads all imports each call; `rocq_start` keeps them warm) |
| Verify a proof matches its stated theorem | `rocq_verify` |
| Audit which axioms a proof depends on | `rocq_assumptions` |
| List definitions / lemmas in a file | `rocq_toc` |
| List notations available at a position | `rocq_notations` |
| Check pet health, memory, recent errors | `rocq_diag` |

## Recommended usage patterns

### Multi-tactic exploration: `rocq_check` then `rocq_step_multi`

To explore N alternative tactics from a known good state, advance the
state with `rocq_check` first, then branch with `rocq_step_multi`:

    # Step 1: confirm the prefix and advance.
    result = rocq_check(from_state=S, body="intros n m H.")
    new_state = result["state_id"]

    # Step 2: try alternatives from that state.
    rocq_step_multi(from_state=new_state, tactics=[
        "by ring.",
        "by lia.",
        "by reflexivity.",
    ])

This is more efficient than passing the prefix repeatedly inside
`tactics=[...]` (each tactic would re-run the prefix).  It also makes
the agent's intent — "I'm confident in the prefix; explore the next
step" — explicit.

### Imports and scopes in `rocq_query`

Statements like `Require Import`, `From X Require Y`, `Open Scope`,
`Set`, `Unset`, `Local`, and `Section` must go in the `preamble=`
parameter (a multi-line string), not in `body=`:

    rocq_query(
        preamble="From Coq Require Import Reals.\nOpen Scope R_scope.",
        command="Search (_ + _).",
    )

Why: each statement in `body=` runs in isolation, so `Open Scope`
in body would not propagate to the next statement.  For multi-import
preambles, prefer `file=<path>` to a `.v` file containing the imports
— more reliable when the imports include `Set` / `Unset` directives
that may need a specific ordering.

For mid-proof queries — e.g. `Search` against the live proof state —
use `from_state=<state_id>` instead of preamble; the live state
already has all imports and scopes set up.

### Failure envelope and `reason` taxonomy

Every failure response carries `{success: False, error: str, reason: str}` so an agent can dispatch on `reason` without parsing message text. The same `reason` is recorded into the `recent_errors` ring buffer that `rocq_diag` returns. Values:

- **Validation / lookup** (set by tools before reaching `pet`): `"validation"`, `"not_found"` (typo on `rocq_start` / `rocq_assumptions`).
- **Pet-side** (set by `_run_with_pet` on subprocess-level failures): `"timeout"`, `"crashed"`, `"memory_exhausted"`, `"lock_contended"`, `"unavailable"`. When pet had to be killed, the response also carries `pet_restarted: True`.
- **`rocq_check` mid-batch**: `"tactic_failed"` (Coq rejected the tactic — distinct from a transport-level `"crashed"`).
- **`rocq_compile` / `rocq_compile_file`**: `"compile_error"` (coqc returned non-zero).
- **`rocq_verify`-specific**: `"compile_error"`, `"axiom_dependency"` (proof relies on `Admitted`/admit/custom axiom), `"type_mismatch"` (Phase 3 found the proof's type differs from the problem's type).

When a tool returns `pet_restarted: True`, call `rocq_diag` for memory headroom and recent-error history.

### Concurrency model

*Background (both audiences):* `rocq-mcp` is **single-tenant per process**.  All agent-facing state — the live `state_id` table, the import cache, the active workspace, and the single `pet` subprocess — is process-global.  Two correctness floors keep concurrent sessions from clobbering each other:

- **LRU-protected state table.** A `state_id` you keep querying via `from_state` will not be evicted by a peer caller churning through new states (see `ROCQ_MAX_STATES`).
- **No implicit current state.** `rocq_check` and `rocq_step_multi` require `from_state` explicitly — there is no global "last touched" state a peer could re-point under you.

The remaining cross-agent costs are pure latency: workspace-swap thrash when peers are on different workspaces, pet RAM growth from accumulated Fleche cache, and the rare case of a peer calling `force_restart=True` (which kills pet under everyone).

**Agent-side recovery: `rocq_start(..., force_restart=True)`.**  When a `state_id` you actively depend on goes missing despite the LRU floor — typically because a peer just force-restarted pet — `rocq_start` with `force_restart=True` is the recovery.  This kills pet, clears the state table, respawns a fresh pet, and returns a new `state_id`.  Note that "fresh" is point-in-time: a different concurrent caller can `force_restart` again right after, so this is recovery, not enforced isolation.  For non-contention triggers (RAM bloat, indexing corruption) the same call applies.

**Orchestrator-side monitoring: `rocq_diag`.**  When you cannot deploy a separate `rocq-mcp` per sub-agent (see the Claude Code escape hatch below for one workaround), `rocq_diag` is the natural primitive for spotting cross-agent interference.  Useful checks between sub-agent dispatches: `live_states[*].file` shows entries created by peer callers (sharing signal when agents are on disjoint files); `memory.pet_rss_mb` against `max_rss_mb_threshold` catches accumulated Fleche bloat before it forces a restart; `recent_errors` shows whether a peer just hit `lock_contended` / `memory_exhausted` / a `force_restart`; `load_average["1m"]` against the host CPU count distinguishes CPU saturation from a diverging tactic when a timeout fires (`None` on platforms without `os.getloadavg`).  Field reports suggest this tool is consistently underused — worth a checklist line in your orchestrator prompt.

**Operator-side hardening:** the cleanest deployment is one `rocq-mcp` subprocess per concurrent agent.  Over stdio this happens naturally when each MCP client launches its own server; the case that needs care is parallel sub-agents within one client, which inherit the parent's MCP connections and share one `rocq-mcp`.  If you're orchestrating parallel Rocq work, prefer separate top-level invocations over one parent with concurrent sub-agents.

*Claude Code escape hatch.*  Sub-agents in `.claude/agents/<name>.md` accept an inline `mcpServers` entry in their frontmatter ([Claude Code docs](https://code.claude.com/docs/en/sub-agents#scope-mcp-servers-to-a-subagent)); an inline definition gives that sub-agent its own `rocq-mcp` subprocess (its own `pet`, `_state_table`, and `current_workspace`), connected when the sub-agent starts and torn down when it finishes.  A string reference instead shares the parent's connection.  Inline definitions let parallel sub-agents each pay the import-load cost once on their own pet rather than thrashing a shared one:

```yaml
mcpServers:
  - rocq-mcp:
      type: stdio
      command: rocq-mcp
```

*Worktree per sub-agent.*  The escape hatch above isolates the `pet` subprocess; for filesystem isolation — so concurrent sub-agents can edit `.v` files without staling each other's interactive sessions (see *Stale file warning* above) — pair the per-sub-agent `mcpServers` entry with a separate `git worktree` per sub-agent, and point `ROCQ_WORKSPACE` at it:

```yaml
mcpServers:
  - rocq-mcp:
      type: stdio
      command: rocq-mcp
      env:
        ROCQ_WORKSPACE: /path/to/worktree-A
```

Each worktree carries its own checkout, its own auto-generated `_RocqProject` (see *Prerequisites*), and its own scratch files — neither sub-agent can clobber the other's interactive sessions through a file edit, and `_RocqProject` regeneration in one worktree does not invalidate the other's load paths.

**Per-call timeout override.**  Pytanque-based tools (those routed through `_run_with_pet`: `rocq_query`, `rocq_start`, `rocq_step_multi`, `rocq_check`, `rocq_assumptions`, `rocq_toc`, `rocq_notations`) accept a `timeout=<seconds>` kwarg that overrides `ROCQ_PET_TIMEOUT` for that one call (clamped to `ROCQ_QUERY_TIMEOUT_CAP`).  On a timeout, prefer bumping `timeout=` per-call rather than raising the global default.

