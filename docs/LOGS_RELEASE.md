# Complete logs: release asset of the private repository

The untracked `logs/` tree (8.4 GB on disk, 174,611 regular files) is published as ONE
zip file, `logs_artifact-2026-09-23.zip` (668.4 MB, sha256 `dca2faaf354e5aab85956acef9203a74ff52015e7afc59b4bbc6a4b80f40141e`), attached to release
`artifact-2026-09-23` of `git@github.com:LLM4Rocq/rocq-mcp-evolve-private.git`, whose tag points at the commit that carries this
manifest. Entries are stored as `logs/...`, so the archive unpacks in place at the repository root;
`python3 harness/results_all_gen.py --check` then reproduces `docs/RESULTS_ALL.md` from it.

Not shipped (A149): the CLI session-file backup directory (`logs/cli_sessions_backup/`, an audit input
whose conclusion is recorded in docs/ASSUMPTIONS.md A142), the per-attempt `cli_session.jsonl` copies
(849 files; the effort value each carried is in its result row, `effort_recorded`, or in
the run's `effort_recovered.jsonl`), `.DS_Store` files, and symbolic links inside attempt work
directories (51).

## Fetch, verify, restore

```sh
gh release download artifact-2026-09-23 --repo LLM4Rocq/rocq-mcp-evolve-private --pattern 'logs_artifact-2026-09-23.zip' --dir /tmp/logs_release
(cd /tmp/logs_release && shasum -a 256 -c "$OLDPWD/docs/logs_release.sha256")
unzip -q /tmp/logs_release/logs_artifact-2026-09-23.zip -d .      # from the repository root; creates ./logs/
python3 harness/results_all_gen.py --check
```

## Contents

| group | files | raw |
|---|---:|---:|
| `logs` | 123 | 1.8 MB |
| `logs/archive` | 462 | 8.0 MB |
| `logs/autoform` | 19,773 | 459.1 MB |
| `logs/audit_autoform` | 55 | 1.4 MB |
| `logs/replay_equivalence` | 2 | 86.1 KB |
| `logs/runs/session_try_hints_v2_minif2f_valid` | 3,268 | 68.8 MB |
| `logs/runs/FINAL_minif2f_test` | 3,794 | 54.7 MB |
| `logs/runs/FINAL_pf_baseline_opus_r245` | 2,337 | 16.5 MB |
| `logs/runs/FINAL_frozen_wallonly` | 4,080 | 181.0 MB |
| `logs/runs/unified_sonnet_dev60` | 823 | 5.4 MB |
| `logs/runs/orp_smoke_luna` | 9 | 20.5 KB |
| `logs/runs/FINAL_pf_rocqmcp_haiku` | 9,183 | 168.1 MB |
| `logs/runs/sweep_session_try_hints_auto_N1` | 192 | 4.7 MB |
| `logs/runs/rocq_mcp_fair2_dev60` | 1,301 | 11.8 MB |
| `logs/runs/session_try_dev60` | 774 | 19.0 MB |
| `logs/runs/sweep_session_try_hints_auto_N8` | 194 | 3.7 MB |
| `logs/runs/winner_ctx_full_inproject60` | 900 | 12.5 MB |
| `logs/runs/rocq_mcp_fair_dev60` | 1,238 | 11.7 MB |
| `logs/runs/baseline_dev60` | 2,411 | 33.2 MB |
| `logs/runs/mstf_evolve_test` | 2,931 | 545.6 MB |
| `logs/runs/baseline_sonnet_dev60` | 1,421 | 6.6 MB |
| `logs/runs/rocq_mcp_smoke` | 32 | 216.2 KB |
| `logs/runs/solo_decomposable` | 382 | 3.5 MB |
| `logs/runs/universal_fable_dev60` | 450 | 1.6 MB |
| `logs/runs/mstp_sota_dev60` | 603 | 1.3 MB |
| `logs/runs/mstp_sota_dev60_v2` | 881 | 3.5 MB |
| `logs/runs/FINAL_pf_baseline_sonnet` | 7,726 | 68.8 MB |
| `logs/runs/winner_ctx_lean_inproject60` | 813 | 19.0 MB |
| `logs/runs/finisher_only_test` | 1,494 | 483.5 KB |
| `logs/runs/orp_smoke_luna_base` | 12 | 38.0 KB |
| `logs/runs/sweep_baseline_N4` | 225 | 3.9 MB |
| `logs/runs/winner_ctx_lean_mathcomp` | 269 | 9.4 MB |
| `logs/runs/_smoke_rocqmcp_haiku_r245` | 12 | 35.9 KB |
| `logs/runs/baseline_fable_dev60` | 730 | 2.2 MB |
| `logs/runs/FINAL_pf_baseline_opus` | 4,857 | 31.4 MB |
| `logs/runs/rocq_mcp_fair2_sonnet_dev60` | 986 | 6.3 MB |
| `logs/runs/sweep_baseline_N2` | 224 | 4.1 MB |
| `logs/runs/FINAL_session_sonnet` | 4,442 | 49.4 MB |
| `logs/runs/smoke_session_1` | 32 | 149.9 KB |
| `logs/runs/orp_smoke_terra` | 9 | 18.9 KB |
| `logs/runs/mcp_timeout_probe` | 9 | 17.4 KB |
| `logs/runs/orp_evolve_test` | 3,313 | 51.6 MB |
| `logs/runs/universal_c30_dev60` | 1,718 | 23.1 MB |
| `logs/runs/team_k3_hard70` | 1,818 | 96.4 MB |
| `logs/runs/solo_hard70` | 1,136 | 54.0 MB |
| `logs/runs/universal_sonnet_dev60` | 848 | 5.2 MB |
| `logs/runs/mstp_evolve_dev60` | 696 | 9.1 MB |
| `logs/runs/PROBE_pf_baseline_sonnet_r245_60` | 711 | 5.4 MB |
| `logs/runs/FINAL_pf_session2_opus` | 3,420 | 517.9 MB |
| `logs/runs/orp_base_test` | 4,773 | 75.5 MB |
| `logs/runs/winner_autofix_dev60` | 909 | 14.1 MB |
| `logs/runs/orp_sib_dev60` | 1,073 | 8.4 MB |
| `logs/runs/FINAL_rocqmcp_sonnet` | 4,601 | 71.9 MB |
| `logs/runs/winner_ctx_lean_ssr_mathcomp` | 256 | 7.0 MB |
| `logs/runs/PROBE_frozen_wallonly_r245_60` | 493 | 15.9 MB |
| `logs/runs/sonnet_native_dev60` | 805 | 4.9 MB |
| `logs/runs/rocq_mcp_dev60` | 1,343 | 11.2 MB |
| `logs/runs/session_dev60` | 738 | 10.0 MB |
| `logs/runs/PROBE_frozen_wallonly_r245_60.void_network` | 173 | 353.2 KB |
| `logs/runs/orp_smoke_luna_sib` | 20 | 74.5 KB |
| `logs/runs/session_try_hints_auto_sugg_dev60` | 1,820 | 21.6 MB |
| `logs/runs/FINAL_pf_baseline_haiku` | 4,854 | 152.9 MB |
| `logs/runs/sweep_session_try_hints_auto_N4` | 185 | 2.7 MB |
| `logs/runs/FINAL_pf_rocqmcp_sonnet` | 4,229 | 46.3 MB |
| `logs/runs/_smoke_haiku_r245` | 8 | 26.1 KB |
| `logs/runs/sweep_session_try_hints_auto_N2` | 191 | 3.3 MB |
| `logs/runs/session_try_compact_dev60` | 771 | 10.6 MB |
| `logs/runs/session_try_search_dev60` | 770 | 12.7 MB |
| `logs/runs/orp_sib_test` | 5,207 | 44.7 MB |
| `logs/runs/finisher_smoke` | 348 | 120.9 KB |
| `logs/runs/FINAL_baseline_sonnet` | 5,796 | 50.8 MB |
| `logs/runs/af_pf_rocqmcp_smoke` | 39 | 176.4 KB |
| `logs/runs/mstp_base_dev60` | 883 | 3.9 GB |
| `logs/runs/_smoke_sonnet_r245` | 14 | 15.6 KB |
| `logs/runs/mstf_base_test` | 3,204 | 45.3 MB |
| `logs/runs/sweep_baseline_N1` | 229 | 3.8 MB |
| `logs/runs/FINAL_pf_session2_sonnet` | 4,013 | 47.2 MB |
| `logs/runs/session_try_hints_dev60` | 789 | 12.3 MB |
| `logs/runs/sweep_baseline_N8` | 230 | 4.1 MB |
| `logs/runs/mstf_sota_test` | 4,241 | 19.0 MB |
| `logs/runs/team_decomposable` | 705 | 3.9 MB |
| `logs/runs/FINAL_pf_rocqmcp_opus` | 4,051 | 34.5 MB |
| `logs/runs/winner_ctx_lean_mc_mathcomp` | 251 | 16.0 MB |
| `logs/runs/orp_evolve_dev60` | 784 | 7.1 MB |
| `logs/runs/unified_dev60` | 907 | 14.0 MB |
| `logs/runs/ctx_lean_fable_mathcomp` | 286 | 4.9 MB |
| `logs/runs/session_try_dev150` | 1,969 | 60.3 MB |
| `logs/runs/winner_auto2_dev60` | 922 | 10.7 MB |
| `logs/runs/ctx_full_fable_mathcomp` | 293 | 4.4 MB |
| `logs/runs/session_try_hints_minif2f_valid` | 2,651 | 109.5 MB |
| `logs/runs/session_try_hints_auto_sonnet_dev60` | 892 | 5.9 MB |
| `logs/runs/_smoke_pf_session2_haiku` | 8 | 25.1 KB |
| `logs/runs/session_try_hints_auto_dev60` | 901 | 21.9 MB |
| `logs/runs/smoke_baseline_1` | 58 | 214.0 KB |
| `logs/runs/FINAL_pf_session_sonnet` | 3,939 | 44.8 MB |
| `logs/runs/mstp_smoke` | 25 | 92.1 KB |
| `logs/runs/winner_ctx_lean_ex_mathcomp` | 268 | 10.3 MB |
| `logs/runs/FINAL_pf_session2_haiku` | 4,165 | 938.6 MB |
| `logs/runs/PROBE_pf_baseline_opus_r245_60` | 135 | 1.2 MB |
| `logs/runs/sonnet_native_auto2_dev60` | 417 | 2.8 MB |
| `logs/runs/rocq_mcp_sonnet_dev60` | 895 | 5.3 MB |
| `logs/runs/_smoke_opus_r245` | 14 | 15.7 KB |
| `logs/runs/orp_base_dev60` | 1,232 | 7.1 MB |
| `logs/runs/rocq_mcp_fair_sonnet_dev60` | 892 | 6.5 MB |
| `logs/runs/universal_dev60` | 1,795 | 32.8 MB |
| `logs/audit_verify` | 32 | 11.0 MB |
| **total** | **174,611** | **8.4 GB** |

Generated by `harness/release_logs.py` on 2026-09-23.
