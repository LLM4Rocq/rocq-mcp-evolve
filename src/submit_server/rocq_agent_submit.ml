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
            let oc = open_out (Filename.concat (Lazy.force workdir) "candidate.v") in
            output_string oc content;
            close_out oc;
            M.text_result
              "Submitted. If it passes external verification it counts as solved. Reply DONE."
              ~log:[ ("content_chars", `Int (String.length content)) ]
        | _ -> M.text_result ~is_error:true "missing required argument: content");
  }

let () = M.run [ submit_tool ]
