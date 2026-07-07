(* Suite A — session server core contracts (see test/ARCHITECTURE.md).
   Every scenario spawns a FRESH session server (sessions are single-task),
   drives it over MCP stdio, asserts on behaviour, and closes it. *)

open Test_helpers.Helpers

module J = Yojson.Safe

(* fixtures live in the source tree; read them from the resolved repo root so
   the location is independent of the process cwd *)
let fixtures_dir = Filename.concat repo_root "test/fixtures"
let fixture name = read_file (Filename.concat fixtures_dir name)

(* fresh workdir with the task file written into it; ROCQ_WORKDIR points here,
   and candidate.v is written here when a proof completes *)
let setup_task content =
  let dir = tmpdir "sessA" in
  let taskfile = Filename.concat dir "task.v" in
  write_file taskfile content;
  (dir, taskfile)

let base_env ~workdir ~taskfile ~tools extra =
  [ ("ROCQ_ENV_V2", "1");
    ("ROCQ_ENABLE_TOOLS", tools);
    ("ROCQ_TASK_FILE", taskfile);
    ("ROCQ_WORKDIR", workdir) ]
  @ extra

let step s text = call s ~name:"step" ~args:(`Assoc [ ("text", `String text) ])
let candidate wd = Filename.concat wd "candidate.v"

let count_substr hay needle =
  let nn = String.length needle in
  if nn = 0 then 0
  else
    let re = Str.regexp_string needle in
    let rec go i acc =
      match Str.search_forward re hay i with
      | j -> go (j + nn) (acc + 1)
      | exception Not_found -> acc
    in
    go 0 0

let ends_with s suf =
  let ls = String.length s and lf = String.length suf in
  ls >= lf && String.sub s (ls - lf) lf = suf

(* ---- A1 commit-good-prefix ------------------------------------------- *)
let a1 () =
  let wd, tf = setup_task (fixture "F2.v") in
  let s = spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step" []) session_exe in
  initialize s;
  let r1 = step s "intros n. bogus_tac." in
  check (contains r1 "1 sentence(s) committed") "A1 commit-good-prefix: 1 sentence committed";
  check (contains r1 "ERROR at `bogus_tac.`") "A1 commit-good-prefix: ERROR at bogus_tac.";
  let r2 = step s "induction n. reflexivity. simpl. rewrite IHn. reflexivity. Qed." in
  check (contains r2 "PROOF COMPLETE") "A1 commit-good-prefix: PROOF COMPLETE";
  let cand = candidate wd in
  check (Sys.file_exists cand) "A1 commit-good-prefix: candidate.v exists";
  let content = if Sys.file_exists cand then read_file cand else "" in
  check (count_substr content "intros n." = 1)
    "A1 commit-good-prefix: committed prefix preserved (intros n. exactly once)";
  close s

(* ---- A2 auto-Qed handshake (atlas fix 1 / A25) ----------------------- *)
let a2 () =
  let wd, tf = setup_task (fixture "F1.v") in
  let s = spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step" []) session_exe in
  initialize s;
  let r = step s "Proof. assert (H := pow2_ge_0 (x^3-1)). nra." in
  check (contains r "PROOF COMPLETE") "A2 auto-Qed handshake: PROOF COMPLETE (no Qed sent)";
  let cand = candidate wd in
  check (Sys.file_exists cand) "A2 auto-Qed handshake: candidate.v exists";
  let content = if Sys.file_exists cand then read_file cand else "" in
  check (ends_with (String.trim content) "Qed.")
    "A2 auto-Qed handshake: candidate ends with Qed. (server issued it)";
  close s

(* ---- A3 try semantics ------------------------------------------------- *)
let a3 () =
  let wd, tf = setup_task (fixture "F1.v") in
  let s = spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"try" []) session_exe in
  initialize s;
  let r =
    call s ~name:"try"
      ~args:
        (`Assoc
          [ ( "candidates",
              `List
                [ `String "bogus.";
                  `String "Proof. nra.";
                  `String "Proof. assert (H := pow2_ge_0 (x^3-1)). nra." ] ) ])
  in
  check (contains r "<< COMMITTED") "A3 try semantics: candidate 3 << COMMITTED";
  check (contains r "error at `bogus") "A3 try semantics: candidate 1 shows an error";
  check (contains r "PROOF COMPLETE") "A3 try semantics: PROOF COMPLETE (auto-Qed) after commit";
  check (Sys.file_exists (candidate wd)) "A3 try semantics: candidate.v exists";
  close s

(* ---- A4 auto_close progress rule (A22 false-winner) ------------------ *)
let a4 () =
  let wd, tf = setup_task (fixture "F3.v") in
  let s =
    spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"auto_close" []) session_exe
  in
  initialize s;
  let r = call s ~name:"auto_close" ~args:(`Assoc []) in
  let no_finisher = contains r "no finisher applies" in
  let closed = contains r "COMMITTED" && contains r "PROOF COMPLETE" in
  check (no_finisher || closed)
    "A4 auto_close progress: real closure or 'no finisher applies' (no no-op win)";
  if no_finisher then
    check (not (Sys.file_exists (candidate wd)))
      "A4 auto_close progress: no candidate.v when no finisher applies";
  close s

(* ---- A5 auto_close synthesis (rung 9b) ------------------------------- *)
let a5 () =
  let wd, tf = setup_task (fixture "F1.v") in
  let s =
    spawn_server
      ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"auto_close" [ ("ROCQ_AUTO2", "1") ])
      session_exe
  in
  initialize s;
  let r = call s ~name:"auto_close" ~args:(`Assoc []) in
  check (contains r "COMMITTED") "A5 auto_close synthesis: COMMITTED";
  check (contains r "PROOF COMPLETE") "A5 auto_close synthesis: PROOF COMPLETE";
  check (contains r "assert (0 <=") "A5 auto_close synthesis: winning script asserts a pow2 hint";
  close s

(* ---- A6 rollback + query non-commit ---------------------------------- *)
let a6 () =
  let wd, tf = setup_task (fixture "F2.v") in
  let s =
    spawn_server
      ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step,rollback,state" [])
      session_exe
  in
  initialize s;
  ignore (step s "intros n.");
  let rq = step s "Search (_ + 0)." in
  check (String.trim rq <> "") "A6 rollback+query: query response non-empty";
  let rb = call s ~name:"rollback" ~args:(`Assoc [ ("count", `Int 1) ]) in
  check (contains rb "rolled back 1") "A6 rollback+query: rolled back 1";
  let st = call s ~name:"state" ~args:(`Assoc []) in
  check (contains st "committed proof: (nothing committed yet)")
    "A6 rollback+query: nothing committed after rollback";
  (* completing the proof must not resurrect the query sentence *)
  ignore (step s "intros n. induction n. reflexivity. simpl. rewrite IHn. reflexivity. Qed.");
  let cand = candidate wd in
  check (Sys.file_exists cand) "A6 rollback+query: candidate.v exists after completion";
  let content = if Sys.file_exists cand then read_file cand else "" in
  check (not (contains content "Search")) "A6 rollback+query: candidate never contains Search";
  close s

(* ---- A7 env-v2 Require rejection ------------------------------------- *)
let a7 () =
  let wd, tf = setup_task (fixture "F2.v") in
  let s =
    spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step,state" []) session_exe
  in
  initialize s;
  let r = step s "Require Import Lia." in
  check (contains r "Require is not allowed") "A7 env-v2: Require is not allowed";
  let st = call s ~name:"state" ~args:(`Assoc []) in
  check (contains st "committed proof: (nothing committed yet)")
    "A7 env-v2: nothing committed after rejected Require";
  close s

(* ---- A8 error enrichment (hints + suggestions) ----------------------- *)
let a8 () =
  let wd, tf = setup_task (fixture "F1.v") in
  let s =
    spawn_server
      ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step" [ ("ROCQ_HINTS", "1"); ("ROCQ_SUGGEST", "1") ])
      session_exe
  in
  initialize s;
  let r1 = step s "norm_num." in
  check (contains r1 "hint:") "A8 error enrichment: hint: on Lean-ism norm_num";
  check (contains r1 "Lean") "A8 error enrichment: identifies norm_num as Lean";
  let r2 = step s "apply Rmult_nonneg." in
  check (contains r2 "near-miss") "A8 error enrichment: near-miss suggestions on unknown ref";
  close s

(* ---- A9 check tool (A24 style-agnostic) ------------------------------ *)
let a9 () =
  let wd, tf = setup_task (fixture "F1.v") in
  let s =
    spawn_server ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"check,step" []) session_exe
  in
  initialize s;
  let r1 = call s ~name:"check" ~args:(`Assoc [ ("script", `String "Proof. nra.") ]) in
  check (contains r1 "ERROR at `nra.`") "A9 check tool: reports error at nra.";
  check (contains r1 "1 sentence(s) committed") "A9 check tool: committed count 1 (Proof.)";
  check (contains r1 "goals:") "A9 check tool: live goal rendered";
  let r2 =
    call s ~name:"check"
      ~args:(`Assoc [ ("script", `String "Proof. assert (H := pow2_ge_0 (x^3-1)). nra. Qed.") ])
  in
  check (contains r2 "PROOF COMPLETE") "A9 check tool: fresh attempt completes";
  close s

(* ---- A10 project loadpaths (A23) ------------------------------------- *)
let a10 () =
  let name = "A10 project loadpaths" in
  let dune_bin = Filename.concat opam_bin "dune" in
  if not (Sys.file_exists dune_bin) then skip name "dune not on PATH"
  else begin
    let proj = tmpdir "sessA_proj" in
    Unix.mkdir (Filename.concat proj "theories") 0o755;
    write_file (Filename.concat proj "dune-project") "(lang dune 3.8)\n(using coq 0.8)\n";
    write_file (Filename.concat proj "theories/dune") "(coq.theory (name TDemo))\n";
    write_file
      (Filename.concat proj "theories/Base.v")
      "Lemma tdemo_add0 : forall n : nat, n + 0 = n. Proof. induction n; simpl; auto. Qed.\n";
    let build_cmd =
      Printf.sprintf "PATH=%s:$PATH %s build --root %s > /dev/null 2>&1"
        (Filename.quote opam_bin) (Filename.quote dune_bin) (Filename.quote proj)
    in
    let rc = Sys.command build_cmd in
    let vo = Filename.concat proj "_build/default/theories/Base.vo" in
    if rc <> 0 || not (Sys.file_exists vo) then
      skip name (Printf.sprintf "dune build of TDemo failed (rc=%d)" rc)
    else begin
      let wd, tf =
        setup_task
          "From TDemo Require Import Base.\n\nTheorem t10 : forall n : nat, (n + 0) + 0 = n.\n"
      in
      let theories = Filename.concat proj "_build/default/theories" in
      let init_args = Printf.sprintf "-Q\n%s\nTDemo" theories in
      let s =
        spawn_server
          ~env:(base_env ~workdir:wd ~taskfile:tf ~tools:"step" [ ("ROCQ_INIT_ARGS", init_args) ])
          session_exe
      in
      initialize s;
      let r = step s "Proof. intros n. rewrite tdemo_add0. apply tdemo_add0. Qed." in
      check (contains r "PROOF COMPLETE") (name ^ ": PROOF COMPLETE with external -Q loadpath");
      close s
    end
  end

(* ---- A11 exemplar retrieval (A27) ------------------------------------ *)
let a11 () =
  let name = "A11 exemplar retrieval" in
  (* Distinctive rare token `foobarqux` guarantees a high-IDF statement match
     so the score clears the >0.8 ranking gate. *)
  let sib =
    "Lemma sib_addz_zero : forall foobarqux : nat, foobarqux + 0 = foobarqux.\n\
     Proof. induction foobarqux; simpl; auto. Qed.\n\n"
  in
  let tgt_stmt =
    "Lemma tgt_addz_zero_twice : forall foobarqux : nat, (foobarqux + 0) + 0 = \
     foobarqux.\n"
  in
  (* the target's OWN proof — lives AFTER the prefix in the same file and must
     never be retrievable (leak-proofing); "now rewrite" is its marker *)
  let tgt_proof = "Proof. intros n. now rewrite <- !plus_n_O. Qed.\n" in
  (* TASK prefix = file content up to and including the target statement line *)
  let prefix = sib ^ tgt_stmt in
  (* project source dir holds the FULL file (prefix is an exact byte-prefix of
     it, so the server flags it same-file and only admits the region before) *)
  let proj = tmpdir "sessA_exempl" in
  write_file (Filename.concat proj "proj.v") (prefix ^ tgt_proof);
  let wd, tf = setup_task prefix in
  let s =
    spawn_server
      ~env:
        (base_env ~workdir:wd ~taskfile:tf ~tools:"state,step"
           [ ("ROCQ_EXEMPLARS", "1"); ("ROCQ_PROJECT_SRC", proj) ])
      session_exe
  in
  initialize s;
  let r1 = call s ~name:"state" ~args:(`Assoc []) in
  check (contains r1 "similar PROVED lemmas")
    (name ^ ": exemplar block delivered on first tool response");
  check (contains r1 "sib_addz_zero") (name ^ ": sibling PROVED lemma retrieved");
  check
    (not (contains r1 "now rewrite"))
    (name ^ ": target's own proof (after prefix) not leaked");
  let r2 = call s ~name:"state" ~args:(`Assoc []) in
  check
    (not (contains r2 "similar PROVED lemmas"))
    (name ^ ": exemplar block pushed exactly once");
  close s

(* ---- A12 runtime `open` tool (no task file) -------------------------- *)
let a12 () =
  let name = "A12 open tool" in
  (* no ROCQ_TASK_FILE: the session starts EMPTY and must be opened at
     runtime with the `open` tool; plain stdlib, no project needed *)
  let wd = tmpdir "sessA12" in
  let file = Filename.concat wd "work.v" in
  write_file file
    "Lemma a12_helper : forall n : nat, n + 0 = n.\n\
     Proof. induction n; simpl; auto. Qed.\n\n\
     Theorem a12_target : forall n : nat, (n + 0) + 0 = n.\n\
     Proof.\n\
     Admitted.\n\n\
     Theorem a12_tail : forall n m : nat, n + m = m + n.\n";
  let s =
    spawn_server
      ~env:
        [ ("ROCQ_WORKDIR", wd);
          ("ROCQ_ENABLE_TOOLS", "open,step,state,auto_close");
          ("ROCQ_EXEMPLARS", "0") ]
      session_exe
  in
  initialize s;
  (* 1. a proof tool BEFORE any open must direct the agent to `open` first *)
  let r0 = call s ~name:"state" ~args:(`Assoc []) in
  check (contains r0 "open") (name ^ ": state before open points at the `open` tool");
  (* 2. open a specific (Admitted) theorem by name *)
  let r1 =
    call s ~name:"open"
      ~args:(`Assoc [ ("file", `String file); ("theorem", `String "a12_target") ])
  in
  check (contains r1 "proving a12_target") (name ^ ": opens a12_target by name");
  check (contains r1 "goals: 1") (name ^ ": a12_target has one goal");
  (* 3. auto_close finishes the opened goal (lia) *)
  let r2 = call s ~name:"auto_close" ~args:(`Assoc []) in
  check (contains r2 "PROOF COMPLETE") (name ^ ": auto_close closes a12_target");
  check (contains r2 "proof script") (name ^ ": completion returns the proof script");
  check (contains r2 "lia") (name ^ ": lia closes a12_target");
  (* 4. open with no theorem => the file's final open statement (a12_tail) *)
  let r3 = call s ~name:"open" ~args:(`Assoc [ ("file", `String file) ]) in
  check (contains r3 "proving the final open statement")
    (name ^ ": no theorem falls to the final open statement");
  (* 5. opening a missing file is a clean error *)
  let r4 = call s ~name:"open" ~args:(`Assoc [ ("file", `String "/nonexistent/x.v") ]) in
  check (contains r4 "no such file") (name ^ ": missing file reported");
  close s

let () =
  a1 ();
  a2 ();
  a3 ();
  a4 ();
  a5 ();
  a6 ();
  a7 ();
  a8 ();
  a9 ();
  a10 ();
  a11 ();
  a12 ();
  summary "suite A"
