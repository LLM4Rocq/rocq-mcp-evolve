(* Sidecar for external-tool configs (A16): the ONLY thing it does is receive
   the agent's final complete .v and write it to $ROCQ_WORKDIR/candidate.v so
   the standard correctness gate can verify it from scratch. No compilation,
   no trust — a wrong submission simply fails the gate. *)

module M = Mcp_core.Mcp_server
module JU = Yojson.Safe.Util

let workdir =
  lazy
    (match Sys.getenv_opt "ROCQ_WORKDIR" with
    | Some d when d <> "" ->
        (try Unix.mkdir d 0o755 with Unix.Unix_error (Unix.EEXIST, _, _) -> ());
        d
    | _ -> Filename.get_temp_dir_name ())

let submit_tool : M.tool =
  {
    name = "submit";
    description =
      "Submit your FINAL complete .v file (imports + statement exactly as \
       given + your proof ending in Qed). Call this exactly once, when you \
       believe the proof is finished — an external checker verifies it from \
       scratch; submissions that don't compile or violate the rules are \
       rejected. This is the only way your proof gets counted.";
    input_schema =
      `Assoc
        [ ("type", `String "object");
          ("properties",
           `Assoc
             [ ("content",
                `Assoc
                  [ ("type", `String "string");
                    ("description", `String "Complete contents of the final .v file") ]) ]);
          ("required", `List [ `String "content" ]) ];
    handler =
      (fun args ->
        match JU.member "content" args with
        | `String content ->
            (* A76 parity: keep every submission versioned. The other arms'
               artifact is effectively their newest COMPILING attempt
               (baseline writes candidate.v only on exit-0; the session
               server only on verified completion) — grading mirrors that
               by taking the newest submission that compiles, so a later
               broken submit can no longer clobber an earlier good one. *)
            let dir = Lazy.force workdir in
            let subs = Filename.concat dir "submissions" in
            (try Unix.mkdir subs 0o755
             with Unix.Unix_error (Unix.EEXIST, _, _) -> ());
            let n = Array.length (Sys.readdir subs) in
            let oc = open_out (Filename.concat subs (Printf.sprintf "%03d.v" n)) in
            output_string oc content;
            close_out oc;
            let oc = open_out (Filename.concat dir "candidate.v") in
            output_string oc content;
            close_out oc;
            M.text_result
              "Submitted. If it passes external verification it counts as solved. Reply DONE."
              ~log:[ ("content_chars", `Int (String.length content)) ]
        | _ -> M.text_result ~is_error:true "missing required argument: content");
  }

let () = M.run [ submit_tool ]
