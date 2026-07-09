(lang dune 3.23)
(name rocq-mcp-evolve)
(generate_opam_files true)
(source (github LLM4Rocq/rocq-tools))
(license Apache-2.0)
(authors "LLM4Rocq")
(maintainers "guillaume.baudart@gmail.com")

(package
 (name rocq-mcp-evolve)
 (synopsis "An MCP server for the Rocq prover, evolved by LLM-driven design search")
 (description
  "An empirically-designed, policy-neutral MCP (Model Context Protocol) server that lets LLM agents drive the Rocq prover: persistent in-process sessions, speculative tactic evaluation, a finisher portfolio with hint synthesis, enriched errors, project load-path auto-discovery, and multi-agent shared-proof support.")
 (depends
  (ocaml (>= 4.14))
  dune
  (rocq-runtime (and (>= 9.1) (< 9.2)))
  memprof-limits
  rocq-stdlib
  yojson)
 (depopts coq-mathcomp-zify coq-mathcomp-algebra-tactics))
