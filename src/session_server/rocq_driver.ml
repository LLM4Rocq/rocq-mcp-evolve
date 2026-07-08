(* In-process Rocq embedding: initialize the prover once, then execute
   vernacular sentences one at a time against explicit Vernacstate.t values.
   State snapshots ARE the backtracking mechanism: every executed sentence
   returns a new state; keeping old ones makes rollback O(1).

   Built directly on the public rocq-runtime API (no STM, no source changes):
   Coqinit for startup, Procq/Pvernac for parsing, Vernacinterp.interp for
   execution, Printer for goal rendering, Control.timeout for per-sentence
   budgets. *)

let initialized = ref false

let prefix_cache : (string * Vernacstate.t) list ref = ref []

(* review fix (live-reproduced staleness): cached prefix snapshots embed
   loaded .vo contents; if any .vo under the project load paths changes on
   disk, the cache must be dropped. We fingerprint (path, mtime, size) of
   .vo files under the init load-path dirs. *)
let loadpath_dirs : string list ref = ref []

let vo_fingerprint () =
  let out = ref [] in
  let rec walk depth d =
    if depth > 4 then ()
    else
      match Sys.readdir d with
      | entries ->
          Array.iter
            (fun e ->
              let p = Filename.concat d e in
              if e = ".git" || e = "_opam" then ()
              else if Sys.is_directory p then walk (depth + 1) p
              else if Filename.check_suffix e ".vo" then
                match Unix.stat p with
                | st -> out := (p, st.Unix.st_mtime, st.Unix.st_size) :: !out
                | exception Unix.Unix_error _ -> ())
            entries
      | exception Sys_error _ -> ()
  in
  List.iter (walk 0) !loadpath_dirs;
  List.sort compare !out

let cache_fingerprint : (string * float * int) list ref = ref []

let check_cache_freshness () =
  if !prefix_cache <> [] then begin
    let now = vo_fingerprint () in
    if now <> !cache_fingerprint then begin
      prefix_cache := [];
      cache_fingerprint := now
    end
  end
  else cache_fingerprint := vo_fingerprint ()


(* set before init by the `open` tool so load-path discovery starts from the
   opened file rather than a launch-time env var *)
let discovery_origin : string option ref = ref None

(* Feedback messages (warnings, Search/Check output, ...) emitted during the
   last exec, oldest first. *)
let messages : string list ref = ref []

let install_feeder () =
  Feedback.warn_no_listeners := false;
  ignore
    (Feedback.add_feeder (fun fb ->
         match fb.Feedback.contents with
         | Feedback.Message (lvl, _loc, _qf, pp) ->
             let tag =
               match lvl with
               | Feedback.Debug -> None
               | Feedback.Info | Feedback.Notice -> Some ""
               | Feedback.Warning -> Some "warning: "
               | Feedback.Error -> Some "error: "
             in
             (match tag with
             | None -> ()
             | Some t -> messages := (t ^ Pp.string_of_ppcmds pp) :: !messages)
         | _ -> ()))

let init () =
  if not !initialized then begin
    Coqinit.init_ocaml ();
    let usage =
      Boot.Usage.
        {
          executable_name = "rocq-agent-session";
          extra_args = "";
          extra_options = "";
        }
    in
    (* real-project support (A23): load-path and other init args arrive
       newline-separated in $ROCQ_INIT_ARGS (e.g. "-Q\n/path\nLogical"),
       exactly as rocq's own CLI would take them. When ROCQ_INIT_ARGS is
       absent, the server discovers them itself (A28): walk up from the task
       file for _CoqProject/_RocqProject (parse -Q/-R/-I) or a dune project
       (coq.theory stanzas -> the _build/default mirror). Zero external
       tooling needed to use the server on a real project. *)
    let discover_project_args () =
      let ( / ) = Filename.concat in
      let task =
        match !discovery_origin with
        | Some f -> f
        | None -> (
            match Sys.getenv_opt "ROCQ_TASK_FILE" with
            | Some f when f <> "" -> f
            | _ -> Sys.getcwd () / "x")
      in
      let rec find_root dir n =
        if n = 0 || dir = "/" || dir = "." then None
        else if Sys.file_exists (dir / "_CoqProject")
                || Sys.file_exists (dir / "_RocqProject")
        then Some (dir, `CoqProject)
        else if Sys.file_exists (dir / "dune-project") then Some (dir, `Dune)
        else find_root (Filename.dirname dir) (n - 1)
      in
      match find_root (Filename.dirname task) 8 with
      | None -> []
      | Some (root, `CoqProject) ->
          let pf =
            if Sys.file_exists (root / "_CoqProject") then root / "_CoqProject"
            else root / "_RocqProject"
          in
          let ic = open_in pf in
          let words = ref [] in
          (try
             while true do
               let line = String.trim (input_line ic) in
               if String.length line > 0 && line.[0] <> '#' then
                 List.iter
                   (fun w -> if w <> "" then words := w :: !words)
                   (Str.split (Str.regexp "[ \t]+") line)
             done
           with End_of_file -> close_in ic);
          let abs d = if Filename.is_relative d then root / d else d in
          let rec take = function
            | "-Q" :: d :: l :: tl -> "-Q" :: abs d :: l :: take tl
            | "-R" :: d :: l :: tl -> "-R" :: abs d :: l :: take tl
            | "-I" :: d :: tl -> "-I" :: abs d :: take tl
            | "-arg" :: a :: tl -> a :: take tl
            | _ :: tl -> take tl
            | [] -> []
          in
          take (List.rev !words)
      | Some (root, `Dune) ->
          (* find dune files with coq.theory stanzas; each maps to the
             _build/default mirror of its directory *)
          let out = ref [] in
          let rec scan dir depth =
            if depth > 5 then ()
            else
              match Sys.readdir dir with
              | entries ->
                  Array.iter
                    (fun e ->
                      let p = dir / e in
                      if e = "_build" || e = ".git" then ()
                      else if Sys.is_directory p then scan p (depth + 1)
                      else if e = "dune" then begin
                        let ic = open_in p in
                        let n = in_channel_length ic in
                        let txt = really_input_string ic n in
                        close_in ic;
                        match Str.search_forward (Str.regexp "coq\\.theory") txt 0 with
                        | exception Not_found -> ()
                        | ti -> (
                          try
                            let _ =
                              Str.search_forward
                                (Str.regexp
                                   "(name[ \t\n]+\\([A-Za-z0-9_.]+\\))")
                                txt ti
                            in
                            let lname = Str.matched_group 1 txt in
                            let rel =
                              if dir = root then ""
                              else
                                String.sub dir
                                  (String.length root + 1)
                                  (String.length dir - String.length root - 1)
                            in
                            let mirror = root / "_build" / "default" / rel in
                            (* mirror when built; else the source dir (in-place
                               builds keep .vo next to .v) *)
                            let dir = if Sys.file_exists mirror then mirror else dir in
                            out := [ "-Q"; dir; lname ] :: !out
                          with Not_found -> ())
                      end)
                    entries
              | exception Sys_error _ -> ()
          in
          scan root 0;
          List.concat (List.rev !out)
    in
    let extra_args =
      match Sys.getenv_opt "ROCQ_INIT_ARGS" with
      | Some s when String.trim s <> "" ->
          String.split_on_char '\n' s
          |> List.map String.trim
          |> List.filter (fun x -> x <> "")
      | _ -> discover_project_args ()
    in
    let rec dirs_of = function
      | ("-Q" | "-R") :: d :: _ :: tl -> d :: dirs_of tl
      | "-I" :: d :: tl -> d :: dirs_of tl
      | _ :: tl -> dirs_of tl
      | [] -> []
    in
    loadpath_dirs := dirs_of extra_args;
    let opts, () =
      Coqinit.parse_arguments
        ~parse_extra:(fun _opts extra -> ((), extra))
        ~initial_args:Coqargs.default extra_args
    in
    Coqinit.init_runtime ~usage opts;
    Coqinit.init_document opts;
    let top = Coqinit.dirpath_of_top opts.Coqargs.config.Coqargs.logic.Coqargs.toplevel_name in
    Coqinit.start_library ~intern:Vernacinterp.fs_intern ~top
      (Coqargs.injection_commands opts);
    install_feeder ();
    initialized := true
  end

let freeze () = Vernacstate.freeze_full_state ()

let proof_open (st : Vernacstate.t) =
  st.Vernacstate.interp.Vernacstate.Interp.lemmas <> None

let n_goals (st : Vernacstate.t) =
  match st.Vernacstate.interp.Vernacstate.Interp.lemmas with
  | None -> 0
  | Some stk ->
      Declare.Proof.get_open_goals (Vernacstate.LemmaStack.get_top stk)

let render_goals (st : Vernacstate.t) =
  match st.Vernacstate.interp.Vernacstate.Interp.lemmas with
  | None -> "(no proof open)"
  | Some stk ->
      Vernacstate.unfreeze_full_state st;
      let p = Declare.Proof.get (Vernacstate.LemmaStack.get_top stk) in
      Pp.string_of_ppcmds (Printer.pr_open_subgoals p)

(* (n focused goals, first-goal conclusion collapsed to one line) *)
let goal_digest (st : Vernacstate.t) =
  match st.Vernacstate.interp.Vernacstate.Interp.lemmas with
  | None -> (0, "")
  | Some stk -> (
      Vernacstate.unfreeze_full_state st;
      let p = Declare.Proof.get (Vernacstate.LemmaStack.get_top stk) in
      let { Proof.sigma; goals; _ } = Proof.data p in
      match goals with
      | [] -> (0, "")
      | g :: _ ->
          let info = Evd.find_undefined sigma g in
          let env = Evd.evar_filtered_env (Global.env ()) info in
          let concl = Evd.evar_concl info in
          let s = Pp.string_of_ppcmds (Printer.pr_econstr_env env sigma concl) in
          let s = String.concat " " (String.split_on_char '\n' s) in
          let s = Str.global_replace (Str.regexp "  +") " " s in
          (List.length goals, s))

let one_line s =
  Str.global_replace (Str.regexp "  +") " "
    (String.concat " " (String.split_on_char '\n' s))

(* Structured view of the FIRST goal: hypotheses as "id : type" strings
   (oldest first) + one-line conclusion; plus conclusions of the other goals. *)
let first_goal_view (st : Vernacstate.t) :
    (string list * string * string list) option =
  match st.Vernacstate.interp.Vernacstate.Interp.lemmas with
  | None -> None
  | Some stk -> (
      Vernacstate.unfreeze_full_state st;
      let p = Declare.Proof.get (Vernacstate.LemmaStack.get_top stk) in
      let { Proof.sigma; goals; _ } = Proof.data p in
      match goals with
      | [] -> Some ([], "", [])
      | g :: rest ->
          let info = Evd.find_undefined sigma g in
          let env = Evd.evar_filtered_env (Global.env ()) info in
          let hyps =
            List.rev_map
              (fun decl ->
                let id = Context.Named.Declaration.get_id decl in
                let ty = Context.Named.Declaration.get_type decl in
                Names.Id.to_string id ^ " : "
                ^ one_line
                    (Pp.string_of_ppcmds (Printer.pr_econstr_env env sigma ty)))
              (Evd.evar_context info)
          in
          let concl =
            one_line
              (Pp.string_of_ppcmds
                 (Printer.pr_econstr_env env sigma (Evd.evar_concl info)))
          in
          let others =
            List.map
              (fun g ->
                match Evd.find_undefined sigma g with
                | info ->
                    let env = Evd.evar_filtered_env (Global.env ()) info in
                    one_line
                      (Pp.string_of_ppcmds
                         (Printer.pr_econstr_env env sigma (Evd.evar_concl info)))
                | exception _ -> "?")
              rest
          in
          Some (hyps, concl, others))

type sentence_result =
  | Ok_st of Vernacstate.t * string list (* new state, messages *)
  | Err of { msg : string; loc : (int * int) option; messages : string list }
  | Timeout of float

let is_qed_like text =
  let t = String.trim text in
  List.exists
    (fun p ->
      String.length t >= String.length p && String.sub t 0 (String.length p) = p)
    [ "Qed"; "Defined"; "Save" ]

(* A35 (user pointer): memprof-limits token interruption as the PRIMARY
   timeout — interruption triggers on ALLOCATION, so it reaches vm_compute /
   native_compute workloads that never hit Control.timeout's checkpoints
   (the same mechanism coq-lsp uses). Control.timeout stays as the inner
   layer for non-allocating checkpointed code. A watchdog thread arms the
   token at the deadline; after an interrupt the summary state is restored
   by the caller's unfreeze, and the interp cache is invalidated. *)
let () = Memprof_limits.start_memprof_limits ()

let exec_sentence ~(timeout_s : float) (st : Vernacstate.t)
    (vc : Vernacexpr.vernac_control) : sentence_result =
  messages := [];
  let token = Memprof_limits.Token.create () in
  let watchdog =
    Thread.create
      (fun () ->
        let deadline = Unix.gettimeofday () +. timeout_s +. 0.5 in
        while
          (not (Memprof_limits.Token.is_set token))
          && Unix.gettimeofday () < deadline
        do
          Thread.delay 0.05
        done;
        if Unix.gettimeofday () >= deadline then
          Memprof_limits.Token.set token)
      ()
  in
  let finish r =
    Memprof_limits.Token.set token;
    Thread.join watchdog;
    r
  in
  match
    Memprof_limits.limit_with_token ~token (fun () ->
        Control.timeout timeout_s
          (fun () -> Vernacinterp.interp ~intern:Vernacinterp.fs_intern ~st vc)
          ())
  with
  | Ok (Some st') -> finish (Ok_st (st', List.rev !messages))
  | Ok None ->
      Vernacstate.Interp.invalidate_cache ();
      finish (Timeout timeout_s)
  | Error _ ->
      (* interrupted by the token: allocation-point interrupt reached code
         Control.timeout could not *)
      Vernacstate.Interp.invalidate_cache ();
      finish (Timeout timeout_s)
  | exception e when CErrors.noncritical e ->
      let e, info = Exninfo.capture e in
      let msg = Pp.string_of_ppcmds (CErrors.iprint (e, info)) in
      let loc = Option.map Loc.unloc (Loc.get_loc info) in
      finish (Err { msg; loc; messages = List.rev !messages })

type exec_step = {
  text : string; (* sentence source text *)
  post : Vernacstate.t;
  msgs : string list;
  ms : float;
  is_query : bool; (* Search/Check/... : no state effect, don't commit *)
}

let query_re = Str.regexp "^[ \t\n]*\\(Search\\|SearchPattern\\|SearchRewrite\\|Check\\|About\\|Print\\|Locate\\|Compute\\|Eval\\|Show\\)\\b"

let is_query_sentence text = Str.string_match query_re text 0


(* A34 (user-reported divergence class): vm_compute/native_compute do not
   reliably hit the interpreter's interrupt checkpoints, so Control.timeout
   cannot stop them (empirically: vm_compute on unary-nat 2016^20214 hangs
   forever). For sentences in this class we first PROBE in a forked child
   under a hard SIGKILL deadline; only a probe that terminates within budget
   is re-executed in-process. Deterministic tactics make the re-execution
   sound; the session state is never touched by the child (COW). *)
let uninterruptible_re =
  Str.regexp "vm_compute\\|native_compute\\|vm_cast_no_check\\|native_cast_no_check"

type probe_outcome = Probe_ok | Probe_err of string | Probe_timeout

let fork_probe ~(timeout_s : float) (st : Vernacstate.t) vc : probe_outcome =
  let rd, wr = Unix.pipe () in
  match Unix.fork () with
  | 0 ->
      (* child: silence output, run, report one status byte + message, die
         via SIGKILL so no at_exit/flush of shared channels runs *)
      Unix.close rd;
      (try
         let devnull = Unix.openfile "/dev/null" [ Unix.O_WRONLY ] 0 in
         Unix.dup2 devnull Unix.stdout;
         Unix.dup2 devnull Unix.stderr
       with Unix.Unix_error _ -> ());
      let code, msg =
        match exec_sentence ~timeout_s st vc with
        | Ok_st _ -> ('0', "")
        | Err { msg; _ } -> ('1', msg)
        | Timeout _ -> ('2', "")
        | exception _ -> ('1', "probe crashed")
      in
      (try
         ignore (Unix.write_substring wr (Printf.sprintf "%c%s" code msg) 0
                   (1 + String.length msg))
       with Unix.Unix_error _ -> ());
      (try Unix.close wr with Unix.Unix_error _ -> ());
      Unix.kill (Unix.getpid ()) Sys.sigkill;
      assert false
  | pid ->
      Unix.close wr;
      let deadline = Unix.gettimeofday () +. timeout_s +. 2.0 in
      let rec wait_child () =
        match Unix.waitpid [ Unix.WNOHANG ] pid with
        | 0, _ ->
            if Unix.gettimeofday () > deadline then begin
              (try Unix.kill pid Sys.sigkill with Unix.Unix_error _ -> ());
              ignore (Unix.waitpid [] pid);
              Probe_timeout
            end
            else begin
              ignore (Unix.select [] [] [] 0.05);
              wait_child ()
            end
        | _ ->
            (* child finished: read its report *)
            let buf = Bytes.create 4096 in
            let n = try Unix.read rd buf 0 4096 with Unix.Unix_error _ -> 0 in
            if n = 0 then Probe_timeout
            else
              let code = Bytes.get buf 0 in
              let msg = Bytes.sub_string buf 1 (n - 1) in
              (match code with
              | '0' -> Probe_ok
              | '1' -> Probe_err msg
              | _ -> Probe_timeout)
      in
      let r = wait_child () in
      (try Unix.close rd with Unix.Unix_error _ -> ());
      r

type exec_stop =
  | Done (* all sentences executed *)
  | Error_at of { text : string; msg : string; loc : (int * int) option; msgs : string list }
  | Timeout_at of { text : string; timeout_s : float }
  | Parse_error of { msg : string; loc : (int * int) option }

(* Execute all sentences of [src] starting from [st]. Returns committed steps
   (in order) and how execution stopped. Parsing is interleaved with execution
   because the parser needs the current proof mode. *)
(* Replay memoization (A30): re-executing text from the SAME starting state
   skips the interpreter for every leading sentence whose text matches the
   previous run, resuming from the cached snapshot at the first divergence.
   Callers pass the cache ONLY when starting from the pristine post-init
   state (prefix loads / open), so cached snapshots are always reachable by
   genuine re-execution. Heavy imports (e.g. the mathcomp bundles) then cost
   once per process instead of once per open. *)
let exec_text ?cache ~(timeout_s : float) ~(qed_timeout_s : float)
    (st : Vernacstate.t) (src : string) : exec_step list * exec_stop =
  let pa =
    Procq.Parsable.make ~loc:(Loc.initial Loc.ToplevelInput)
      (Gramlib.Stream.of_string src)
  in
  let sentence_text loc =
    match loc with
    | None -> "<sentence>"
    | Some l ->
        let b, e = Loc.unloc l in
        let b = max 0 b and e = min (String.length src) e in
        if e > b then String.sub src b (e - b) else "<sentence>"
  in
  let save acc =
    match cache with
    | Some c ->
        let cur = List.rev_map (fun x -> (x.text, x.post)) acc in
        (* review fix: a run that is a strict text-prefix of the cache (e.g.
           make_session replaying part of open's full-file pass, or a failed
           open of a broken file) must not truncate or wipe the warm cache *)
        let rec is_prefix a b =
          match (a, b) with
          | [], _ -> true
          | (ta, _) :: a', (tb, _) :: b' -> String.equal ta tb && is_prefix a' b'
          | _ :: _, [] -> false
        in
        if not (is_prefix cur !c) then c := cur
    | None -> ()
  in
  let rec loop st remaining_cache acc =
    Vernacstate.unfreeze_full_state st;
    let pm =
      if proof_open st then Some (Synterp.get_default_proof_mode ()) else None
    in
    match Procq.Entry.parse (Pvernac.main_entry pm) pa with
    | exception e when CErrors.noncritical e ->
        let e, info = Exninfo.capture e in
        save acc;
        ( List.rev acc,
          Parse_error
            {
              msg = Pp.string_of_ppcmds (CErrors.iprint (e, info));
              loc = Option.map Loc.unloc (Loc.get_loc info);
            } )
    | None ->
        save acc;
        (List.rev acc, Done)
    | Some vc -> (
        let text = sentence_text vc.CAst.loc in
        match remaining_cache with
        | (ctext, cpost) :: ctl when String.equal ctext text ->
            (* cache hit: skip the interpreter, adopt the cached snapshot *)
            loop cpost ctl
              ({ text; post = cpost; msgs = []; ms = 0.;
                 is_query = is_query_sentence text }
              :: acc)
        | _ ->
            let tmo = if is_qed_like text then qed_timeout_s else timeout_s in
            let t0 = Unix.gettimeofday () in
            let guarded () =
              (* A35: memprof-limits token interruption (inside exec_sentence)
                 is the primary guard and empirically stops vm_compute /
                 native_compute divergence. The fork-probe remains available
                 as an opt-in belt (ROCQ_FORK_PROBE=1) for zero-state-risk
                 contexts. *)
              let needs_probe =
                Sys.getenv_opt "ROCQ_FORK_PROBE" = Some "1"
                && (try
                      ignore (Str.search_forward uninterruptible_re text 0);
                      true
                    with Not_found -> false)
              in
              if not needs_probe then exec_sentence ~timeout_s:tmo st vc
              else
                match fork_probe ~timeout_s:tmo st vc with
                | Probe_ok -> exec_sentence ~timeout_s:tmo st vc
                | Probe_err msg -> Err { msg; loc = None; messages = [] }
                | Probe_timeout -> Timeout tmo
            in
            (match guarded () with
            | Ok_st (st', msgs) ->
                let ms = (Unix.gettimeofday () -. t0) *. 1000. in
                loop st' []
                  ({ text; post = st'; msgs; ms;
                     is_query = is_query_sentence text }
                  :: acc)
            | Err { msg; loc; messages } ->
                save acc;
                (List.rev acc, Error_at { text; msg; loc; msgs = messages })
            | Timeout t ->
                save acc;
                (List.rev acc, Timeout_at { text; timeout_s = t })))
  in
  (match cache with Some _ -> check_cache_freshness () | None -> ());
  loop st (match cache with Some c -> !c | None -> []) []

