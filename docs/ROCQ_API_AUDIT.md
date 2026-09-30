# Rocq-API audit of the session server

Audit of 2026-09-03 (follow-up to trail entry A122). Question: where does the server handle
Rocq source or Rocq objects through strings, pretty-printed output, subprocesses, or
re-execution, when the linked rocq-runtime 9.1.1 offers a typed way that is cleaner, more
robust, and no slower? Method: seven readers surveyed every file of `src/` in chunks and
catalogued each Rocq-handling site; forty-nine skeptics then checked each proposed API
against the installed `.mli` and tried to demonstrate the failure, most of them live
through `scripts/mcp_repl.py`. Machine-readable evidence: `docs/rocq_api_audit.json`
(every site and verdict with file:line and `.mli:line` anchors).

Census: 87 sites; 26 already use the runtime API properly; 61 do not. Of those, 49 were
verified: 45 confirmed (29 bugs, 16 robustness after the skeptics re-graded), 4 downgraded.
Every "bug" below has a demonstrated failing input.

## Impact on recorded results: none found

The held-out miniF2F arms exposed only `step / rollback / state / try / auto_close`, so most
sites below were unreachable there. For the reachable ones a census of the server logs and
graded artifacts of the `FINAL_*` session arms shows: the ten `Require is not allowed`
rejections were all real `Require` commands (the comment-triggered false rejection never
fired); no solved candidate contains a committed query sentence; exemplar retrieval was off
in every measured configuration; the load-path staleness needs project mode, where grading
recompiles from scratch. Fixes are therefore product-path changes; each rebuild of the
session binary gets a trail entry (A122 precedent).

## Six API adoptions cover most of the findings

| adopt | replaces | sites |
|---|---|---|
| a parsed-sentence walk (`Pvernac.main_entry` / `Procq.Entry.parse`, which `exec_text` already uses) | `qed_re` closer skip on raw text, `lemma_re` statement scans, `skip_to_next_block`, `stmt_re_of`, `block_name`, `strip_comments` | open, build, exemplars |
| `Vernacstate.LemmaStack` + `Declare.Proof.get_name` (done in A122 for build's EOF hole) | remaining keyword-based "which theorem is open" scans | open, build, task tail |
| `Vernac_classifier.classify_vernac` (`VtQuery`, proof-ending classes) | `query_re` / `is_query_sentence`, `is_qed_like` | driver, every step |
| a typed error surface in `exec_sentence` (keep the exception: `Nametab.GlobalizationError qid`, `Pretype_errors.VarNotFound`, syntax errors) | `unknown_ref_re`, `hint_for`, `ssr_hint` grepping rendered messages | hints, suggestions |
| `Library.loaded_libraries` / `Loadpath.get_load_paths` after init | `mentions_mathcomp`, `import_echo` substring checks on prefix text, `dirs_of` hand-parse, whole-tree `.vo` walk | session start, completion message, cache freshness |
| `Search.interface_search` (typed hits) | newline-splitting of `Search` feedback, first-`:` name recovery, string "flip" of `>`/`<` in the query | search, suggest_names |

Plus, for the multi-agent daemon: goal identity by `Evar.t` (`Proof.data.goals`, `Evar.equal`)
instead of printed-conclusion strings and positional indices.

## Tier 1: bugs on the product path (fix first)

| site | what breaks | API |
|---|---|---|
| `reject_require` (`rocq_agent_session.ml:160-169`, called from step/try/check) | `(* Require: ... *) reflexivity.` rejected under `ROCQ_ENV_V2` because the word appears in a comment | parse, then refuse only `VernacSynterp (VernacRequire _)` (`vernac/vernacexpr.mli:377`) |
| `is_query_sentence` (`rocq_driver.ml:394-396`) | `Time Search nat.` and `Redirect "f" Search nat.` are committed into the proof script | `Vernac_classifier.classify_vernac = VtQuery` (`vernac/vernac_classifier.mli:16`) |
| load-path fingerprint (`rocq_driver.ml:19, 21-53, 204-210`) | only literal `-Q/-R/-I` args are watched; implicit paths (`.`, stdlib, user-contrib) never; with no project file nothing is watched, so a recompiled dependency leaves a stale prefix cache and a false theorem is reported proved | `Loadpath.get_load_paths` + `physical` after init (`vernac/loadpath.mli:26,32`); fingerprint only `Library.loaded_libraries ()` via `locate_absolute_library` |
| search entries split on newlines (`:1010-1024`) | a hit whose statement wraps counts as several hits; truncation cuts mid-hit; counts wrong on ordinary queries | count `Search.interface_search` objects, not lines (`vernac/search.mli:75`) |
| search direction "flip" (`:993-1007`) | `Str.global_replace` of `> ` and `>=` in the raw query corrupts it (live: syntax error returned) | drop; express the alternative as a second typed pattern |
| `suggest_names` (`:592-638`) | runs `Search "frag".` as a vernacular per fragment and re-parses the first line before the first `:`; suggestions vanish under `Set Search Output Name Only` or any hit without `:` | `Search.interface_search` with `Name_Pattern` |
| `hint_for` / `unknown_ref_re` / `ssr_hint` (`:355-472, 640-654`) | error kind decided by substrings of the rendered message; qualified names (`Foo.Bar.x`) get no suggestion; `Simp.` vs `simp` case mismatch | catch the typed exception in `exec_sentence` and return its kind and qualid |
| `qed_re` closer skip (`:1592-1594, 1647-1653`; duplicate in build `:1858-1863`) | searches raw text for the next `Qed.` after an admitted proof; a `Qed.` inside a comment resumes the walk in the wrong place | resume at the next parsed sentence |
| `strip_comments` (`:1331-1355`) | tracks strings only inside comments; a `(*` inside a top-level string literal opens a phantom comment; used by the `verify` forbidden-token gate | `CLexer` tokens (`parsing/cLexer.mli:71`) |
| `mentions_mathcomp` / `import_echo` (`:82-84, 306-341`) | the substring `mathcomp` or `Lra` in a comment triggers a 60-module preload or suppresses the import reminder | `Library.loaded_libraries` (`vernac/library.mli:74`) |
| exemplars (`:1326-1391, 1416-1420, 1454-1469`) | regex lemma extraction over unexecuted files (missing `Qed.` merges blocks); byte-prefix identity lets a target's own later proof be served back under `ROCQ_EXEMPLARS=1` | `Procq.parse_string` over `vernac_control`; identity by parsed statement |
| `verify` token scan (`:1934-1971`) | source-text regex for admit/Axiom/... reports `VERIFY FAILED` with `build_ok=true` on false positives | `Assumptions.assumptions` on the compiled theorems (`vernac/assumptions.mli:32`) |
| daemon goal ownership (`rocq_agent_daemon.ml:126-139, 199-252`) | branches matched to trunk goals by printed-conclusion equality and positional ids; duplicate conclusions or reordering mis-assign owners (reproduced live) | `Evar.t` identity (`kernel/evar.mli:19,26`) |
| files server `verify` (`rocq_agent_files.ml:152-224`) | same hand-rolled comment stripper; odd quote counts break it | `CLexer` |

## Tier 2: robustness and performance

- Goal diff for the compact renderer by string equality of printed hypotheses (`:204-229`): use `Printer.pr_open_subgoals ~diffs` / `Proof_diffs` (`printing/printer.mli:203`).
- `power_terms`, `r_vars_of_state` (`:497-533`): regex over printed conclusions and types; use `EConstr.decompose_app` / named context.
- `goal_digest_flatten` (`rocq_driver.ml:91-107`): regex normalisation of `Pp` output; use `Pp.pp_with` with a fixed formatter.
- `vo_fingerprint` (`rocq_driver.ml:21-53`): stats every `.vo` under every load path on every step; fingerprint only loaded libraries.
- `dune_theory_scan` (`rocq_driver.ml:160-189`): only the first `coq.theory` stanza per dune file; no runtime API exists, needs a real s-expression parse.
- `stmt_tokens` / `ident_re`, `exemplar_dirs_argv`, `cross_project_loadpath_check`: minor, same replacements as above.

## Justified as is

- `proc.ml` and `fork_probe`: external `rocq compile` processes and the opt-in probe cannot use in-process APIs; memprof-limits is already the primary guard (A35).
- `uninterruptible_re`: no runtime predicate identifies `vm_compute`-class sentences; keep, document.
- `proof_script` / completion message: the text is the deliverable the agent inserts.
- The control server's exit-code-only acceptance of `candidate.v`: by design, grading is the gate's job.

## Suggested order

1. Driver first: typed error surface, `classify_vernac`, `Loadpath`/`Library`-based fingerprint. These are hot-path and behaviour-preserving for correct inputs.
2. `reject_require` on the AST (changes a verdict only for comment-triggered rejections, which never occurred in measured runs).
3. Parsed-sentence walk shared by `open` and `build`, removing `qed_re`, `lemma_re`, `strip_comments` there.
4. Search and suggestions on `Search.interface_search`.
5. Exemplars and the daemon.

Each step: `dune runtest`, a regression case in `test/test_session.ml`, and a trail entry.

## Status (2026-09-03, trail A123 and A124)

Fixed: every Tier 1 item and the Tier 2 items on typed terms and goals, in
two steps: the driver package (A123: typed error kinds, the classifier for
query/closer/statement sentences, AST-level Require policy, loaded-library
fingerprint, Tacenv-based tactic visibility) and six delegated, reviewed
packages (A124: parsed open/build walk, typed Search, parsed exemplars,
evar-identity daemon, lexer-token verify, typed term handling). Suite A
grew from 57 to 113 checks, suite B from 35 to 44.

Left, with the reason: the dune stanza scanner and the `_CoqProject`
parser (no runtime API; need a real s-expression / project-file parser),
the `vm_compute` sentence regex (no runtime predicate), `proc.ml` and the
opt-in fork probe (external processes), the files server's stripper (not
linked against the runtime; made symmetric instead), an explicitly
`Admitted` lemma reported as neither block nor hole, and an unclosed
`Section`/`Module` at end of file.

## Status (2026-09-07, trail A134): second pass over the session server

Every remaining regex or string hack in `src/session_server/` that a
runtime API can replace is replaced; suite A 146 -> 165.

| site | was | now |
|---|---|---|
| `one_line` (driver) | `Str.global_replace "  +"` over printed terms | `pp_one_line`: one oversized-margin `Format` print, no flatten (`goal_digest`, `first_goal_view`, `hyp_delta`) |
| `import_echo` | word-boundary regexes over the proof script | `CLexer` identifier tokens (`lex_fold` / `idents_of`); a name in a comment or string no longer echoes |
| `closer_available` | strip `by `/`now `/`intros. ` then head word | every library tactic token in the candidate must be visible (`words_of`) |
| `search` head check | `^Search\b` regex | first lexer token is the `Search` keyword |
| `stmt_tokens` | identifier regex + stop-word list | lexer identifiers; keywords never reach the list |
| `block_name` (`build` fallback) | `Lemma\|Theorem\|...` regex then identifier | `statement_name` on the parsed sentence: Theorem/Definition/Fixpoint/CoFixpoint/Instance/DeclareInstance names from the AST |
| exemplar leak guard | name removed by regex, whitespace-normalised text compare | `stmt_sig` (binders, type) from `parse_units`, compared with `Constrexpr_ops.local_binder_eq` / `constr_expr_eq` |
| `open` Admitted count | `Admitted` regex over step text | `VtQed (VtKeep VtKeepAxiom)` class of the executed step |
| `pow_terms` exponent | print, strip `%nat`, `int_of_string` | `nat_literal`: walk `S`/`O` via `num.nat.S` / `num.nat.O` (`Rocqlib.lib_ref_opt`); atomic base by `EConstr.kind`, not by a space in the rendering |
| `_CoqProject` | line split on whitespace, hand `-Q/-R/-I/-arg` | `CoqProject_file.read_project_file` (the `rocq makefile` reader) |
| dune stanzas | two `Str.regexp` searches, first stanza only | a small s-expression reader; every `coq.theory` / `rocq.theory` stanza |
| `skip_stray_terminator` | character scan for blanks then `.` | first lexer token is `KEYWORD "."` (comments before it are skipped too) |
| unclosed `Section`/`Module` at EOF | not reported | `Lib.sections_are_opened` / `Lib.is_module_or_modtype`, named by `Lib.current_dirpath` (`build` hole) |
| exemplar file walk | local copy | `Mcp_core.Project_verify.v_files` (`_opam` now skipped everywhere) |

Still string-based, each with its reason: `search_names_containing` builds a
`Str.regexp` because `Search.Name_Pattern` takes one; `first_word` in the
hint tables runs on agent text that may not be Rocq at all (Lean syntax,
`exact?`), so the Rocq lexer is the wrong tool there; four `hint_for`
message checks (`[ltac_use_default] expected`, `Lexer: Undefined token`, `No
product even after head-reduction`, `not a valid ring equation`) key on
`UserError` / grammar-error text with no typed constructor (`CLexer.Error.t`
is abstract); the s-expression reader is not a runtime API because dune has
none; `Str.string_after` in open/build is plain offset slicing on
`Loc`-derived positions. The `vm_compute` regex, `proc.ml` and the files
server's stripper stay as recorded above.
