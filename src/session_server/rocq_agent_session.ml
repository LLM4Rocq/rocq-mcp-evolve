(* Config "session": persistent in-process prover session.

   The theorem's file prefix ($ROCQ_TASK_FILE) is executed once at startup;
   after that the agent drives the open proof with:
     step{text}      — execute proof sentences incrementally; good sentences
                       commit permanently, the first failing one reports a
                       structured error; queries (Search/Check/...) also work
     rollback{count} — undo the last N committed sentences (O(1) state swap)
     state{}         — re-render current goals
   candidate.v is written whenever the proof completes (harness contract). *)

module M = Mcp_core.Mcp_server
module D = Rocq_driver
module JU = Yojson.Safe.Util

let getenv_f name default =
  match Sys.getenv_opt name with
  | Some s -> (try float_of_string s with _ -> default)
  | None -> default

let step_timeout = lazy (getenv_f "ROCQ_STEP_TIMEOUT" 10.)
let qed_timeout = lazy (getenv_f "ROCQ_QED_TIMEOUT" 60.)

let workdir =
  lazy
    (match Sys.getenv_opt "ROCQ_WORKDIR" with
    | Some d when d <> "" ->
        (try Unix.mkdir d 0o755 with Unix.Unix_error (Unix.EEXIST, _, _) -> ());
        d
    | _ -> Filename.get_temp_dir_name ())

type session = {
  mutable committed : (string * Vernacstate.t) list; (* newest first *)
  mutable base : Vernacstate.t;
  mutable complete : bool;
  prefix : string;
}

let session : session option ref = ref None

let cur_state s =
  match s.committed with (_, st) :: _ -> st | [] -> s.base

(* Lazy one-time startup: init prover, execute the task prefix. *)
let get_session () =
  match !session with
  | Some s -> s
  | None ->
      let prefix_file =
        match Sys.getenv_opt "ROCQ_TASK_FILE" with
        | Some f when f <> "" -> f
        | _ -> failwith "ROCQ_TASK_FILE not set"
      in
      let ic = open_in_bin prefix_file in
      let prefix = really_input_string ic (in_channel_length ic) in
      close_in ic;
      D.init ();
      let st0 = D.freeze () in
      let steps, stop =
        D.exec_text ~timeout_s:120. ~qed_timeout_s:120. st0 prefix
      in
      (match stop with
      | D.Done -> ()
      | D.Error_at { text; msg; _ } ->
          failwith (Printf.sprintf "task prefix failed at %S: %s" text msg)
      | D.Timeout_at { text; _ } ->
          failwith (Printf.sprintf "task prefix timed out at %S" text)
      | D.Parse_error { msg; _ } ->
          failwith (Printf.sprintf "task prefix parse error: %s" msg));
      let base =
        match List.rev steps with s :: _ -> s.D.post | [] -> st0
      in
      let s = { committed = []; base; complete = false; prefix } in
      session := Some s;
      s

let goals_block st =
  let n = D.n_goals st in
  if not (D.proof_open st) then "(no proof open)"
  else Printf.sprintf "goals: %d\n%s" n (D.render_goals st)

let write_candidate s =
  let sentences = List.rev_map fst s.committed in
  let body = String.concat "\n" sentences in
  let oc = open_out (Filename.concat (Lazy.force workdir) "candidate.v") in
  output_string oc (s.prefix ^ "\n" ^ body ^ "\n");
  close_out oc

let fmt_msgs msgs =
  match msgs with
  | [] -> ""
  | ms -> String.concat "\n" ms ^ "\n"

let step_tool : M.tool =
  {
    name = "step";
    description =
      "Execute one or more Rocq sentences in the live proof session (tactics \
       like `intros.` `nra.`, structure like `Proof.` `Qed.`, or queries like \
       `Search (_ + _)%R.` `Check Rmult_le_compat.`). Sentences run in order; \
       each success is committed permanently. On the first failure execution \
       stops: earlier sentences of this call STAY committed, the error is \
       reported, and the goal state shown is the one after the last success. \
       End the proof with `Qed.`";
    input_schema =
      `Assoc
        [ ("type", `String "object");
          ("properties",
           `Assoc
             [ ("text",
                `Assoc
                  [ ("type", `String "string");
                    ("description",
                     `String "Rocq sentences to execute, separated by spaces or newlines") ]) ]);
          ("required", `List [ `String "text" ]) ];
    handler =
      (fun args ->
        let s = get_session () in
        if s.complete then
          M.text_result
            "The proof is already COMPLETE. Reply DONE — do not call more tools."
        else
          match JU.member "text" args with
          | `String text ->
              let st = cur_state s in
              let t0 = Unix.gettimeofday () in
              let steps, stop =
                D.exec_text ~timeout_s:(Lazy.force step_timeout)
                  ~qed_timeout_s:(Lazy.force qed_timeout) st text
              in
              let prover_ms = (Unix.gettimeofday () -. t0) *. 1000. in
              List.iter
                (fun (st : D.exec_step) ->
                  s.committed <- (st.text, st.post) :: s.committed)
                steps;
              let n_ok = List.length steps in
              let all_msgs =
                List.concat_map (fun (x : D.exec_step) -> x.msgs) steps
              in
              let now = cur_state s in
              let body =
                match stop with
                | D.Done ->
                    if not (D.proof_open now) && n_ok > 0 then begin
                      s.complete <- true;
                      write_candidate s;
                      Printf.sprintf
                        "%sok: %d sentence(s) committed.\nPROOF COMPLETE — the \
                         file is saved. Reply DONE."
                        (fmt_msgs all_msgs) n_ok
                    end
                    else
                      Printf.sprintf "%sok: %d sentence(s) committed.\n%s"
                        (fmt_msgs all_msgs) n_ok (goals_block now)
                | D.Error_at { text; msg; loc = _; msgs } ->
                    Printf.sprintf
                      "%s%d sentence(s) committed, then ERROR at `%s`:\n%s\n\n\
                       state unchanged since last success:\n%s"
                      (fmt_msgs (all_msgs @ msgs))
                      n_ok (String.trim text) msg (goals_block now)
                | D.Timeout_at { text; timeout_s } ->
                    Printf.sprintf
                      "%s%d sentence(s) committed, then TIMEOUT (>%gs) at `%s` \
                       — this tactic is too slow here; try something else.\n%s"
                      (fmt_msgs all_msgs) n_ok timeout_s (String.trim text)
                      (goals_block now)
                | D.Parse_error { msg; _ } ->
                    Printf.sprintf
                      "%s%d sentence(s) committed, then SYNTAX ERROR:\n%s"
                      (fmt_msgs all_msgs) n_ok msg
              in
              let stop_kind =
                match stop with
                | D.Done -> "done"
                | D.Error_at _ -> "error"
                | D.Timeout_at _ -> "timeout"
                | D.Parse_error _ -> "parse_error"
              in
              M.text_result body
                ~log:
                  [ ("prover_ms", `Float prover_ms);
                    ("sentences_ok", `Int n_ok);
                    ("stop", `String stop_kind);
                    ("n_goals", `Int (D.n_goals now));
                    ("complete", `Bool s.complete) ]
          | _ -> M.text_result ~is_error:true "missing required argument: text");
  }

let rollback_tool : M.tool =
  {
    name = "rollback";
    description =
      "Undo the last N committed sentences and show the goal state you are \
       back to.";
    input_schema =
      `Assoc
        [ ("type", `String "object");
          ("properties",
           `Assoc
             [ ("count",
                `Assoc
                  [ ("type", `String "integer");
                    ("description", `String "How many sentences to undo (default 1)") ]) ]);
          ("required", `List []) ];
    handler =
      (fun args ->
        let s = get_session () in
        let count =
          match JU.member "count" args with `Int n when n > 0 -> n | _ -> 1
        in
        let rec drop n l = if n <= 0 then l else match l with [] -> [] | _ :: t -> drop (n - 1) t in
        let before = List.length s.committed in
        s.committed <- drop count s.committed;
        s.complete <- false;
        let dropped = before - List.length s.committed in
        let now = cur_state s in
        Vernacstate.unfreeze_full_state now;
        M.text_result
          (Printf.sprintf "rolled back %d sentence(s). %d remain committed.\n%s"
             dropped (List.length s.committed) (goals_block now))
          ~log:[ ("rolled_back", `Int dropped) ]);
  }

let state_tool : M.tool =
  {
    name = "state";
    description = "Show the current proof state (all open goals) and the committed proof so far.";
    input_schema =
      `Assoc [ ("type", `String "object"); ("properties", `Assoc []) ];
    handler =
      (fun _args ->
        let s = get_session () in
        let now = cur_state s in
        let proof_so_far =
          match s.committed with
          | [] -> "(nothing committed yet)"
          | l -> String.concat " " (List.rev_map fst l)
        in
        M.text_result
          (Printf.sprintf "committed proof: %s\n%s%s" proof_so_far
             (if s.complete then "PROOF COMPLETE.\n" else "")
             (goals_block now)));
  }

let () = M.run [ step_tool; rollback_tool; state_tool ]
