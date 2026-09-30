(* Minimal file-workspace MCP sidecar for the phase-2 (autoformalization)
   experiment. ALL experiment arms get exactly these tools, so the measured
   delta between arms is the attached prover-server tools alone.
   Evaluation scaffolding — not shipped as a product library.
   Workspace root: $ROCQ_WORKSPACE (all paths are relative to it; escapes
   are rejected). *)

module M = Mcp_core.Mcp_server
module JU = Yojson.Safe.Util

let root =
  lazy
    (match Sys.getenv_opt "ROCQ_WORKSPACE" with
    | Some d when d <> "" -> d
    | _ -> failwith "ROCQ_WORKSPACE not set")

let resolve rel =
  if String.length rel > 0 && rel.[0] = '/' then None
  else if
    List.exists (fun seg -> seg = "..") (String.split_on_char '/' rel)
  then None
  else Some (Filename.concat (Lazy.force root) rel)

let rec mkdirs d =
  if d <> "/" && d <> "." && not (Sys.file_exists d) then begin
    mkdirs (Filename.dirname d);
    (try Unix.mkdir d 0o755 with Unix.Unix_error (Unix.EEXIST, _, _) -> ())
  end

let write_tool : M.tool =
  {
    name = "write_file";
    description =
      "Create or overwrite a file in the project workspace. Path is \
       relative to the workspace root (e.g. theories/Spec.v). Parent \
       directories are created automatically.";
    input_schema =
      `Assoc
        [ ("type", `String "object");
          ( "properties",
            `Assoc
              [ ("path", `Assoc [ ("type", `String "string") ]);
                ("content", `Assoc [ ("type", `String "string") ]) ] );
          ("required", `List [ `String "path"; `String "content" ]) ];
    handler =
      (fun args ->
        let path = JU.member "path" args |> JU.to_string in
        let content = JU.member "content" args |> JU.to_string in
        match resolve path with
        | None -> M.text_result ~is_error:true "path must be relative, no .."
        | Some abs ->
            mkdirs (Filename.dirname abs);
            let oc = open_out abs in
            output_string oc content;
            close_out oc;
            M.text_result
              (Printf.sprintf "wrote %s (%d bytes)" path
                 (String.length content)));
  }

let read_tool : M.tool =
  {
    name = "read_file";
    description = "Read a file from the workspace (relative path).";
    input_schema =
      `Assoc
        [ ("type", `String "object");
          ( "properties",
            `Assoc [ ("path", `Assoc [ ("type", `String "string") ]) ] );
          ("required", `List [ `String "path" ]) ];
    handler =
      (fun args ->
        let path = JU.member "path" args |> JU.to_string in
        match resolve path with
        | None -> M.text_result ~is_error:true "path must be relative, no .."
        | Some abs ->
            if not (Sys.file_exists abs) then
              M.text_result ~is_error:true ("no such file: " ^ path)
            else begin
              let ic = open_in_bin abs in
              let s = really_input_string ic (in_channel_length ic) in
              close_in ic;
              M.text_result s
            end);
  }

let list_tool : M.tool =
  {
    name = "list_dir";
    description = "List the workspace tree (paths relative to the root).";
    input_schema =
      `Assoc [ ("type", `String "object"); ("properties", `Assoc []) ];
    handler =
      (fun _ ->
        let buf = Buffer.create 256 in
        let rec walk rel abs =
          match Sys.readdir abs with
          | entries ->
              Array.sort compare entries;
              Array.iter
                (fun e ->
                  if e <> "_build" && e.[0] <> '.' then begin
                    let r = if rel = "" then e else rel ^ "/" ^ e in
                    let a = Filename.concat abs e in
                    if Sys.is_directory a then walk r a
                    else Buffer.add_string buf (r ^ "\n")
                  end)
                entries
          | exception Sys_error _ -> ()
        in
        walk "" (Lazy.force root);
        let s = Buffer.contents buf in
        M.text_result (if s = "" then "(empty workspace)" else s));
  }

let build_tool : M.tool =
  {
    name = "dune_build";
    description =
      "Run `dune build` at the workspace root and return its full output \
       (all errors across all files).";
    input_schema =
      `Assoc [ ("type", `String "object"); ("properties", `Assoc []) ];
    handler =
      (fun _ ->
        (* A40 robustness: concurrent dune builds on one workspace race on
           dune's global lock (loser errors confusingly). Serialize builds
           across the team's sidecar processes with an flock on the
           workspace — callers queue instead of failing. *)
        let lock_path = Filename.concat (Lazy.force root) ".team_build_lock" in
        let fd = Unix.openfile lock_path [ Unix.O_CREAT; Unix.O_WRONLY ] 0o644 in
        Unix.lockf fd Unix.F_LOCK 0;
        let r =
          Mcp_core.Proc.run ~timeout_s:240.
            ~cwd:(Lazy.force root)
            [| "dune"; "build"; "--root"; "." |]
        in
        (try Unix.lockf fd Unix.F_ULOCK 0; Unix.close fd
         with Unix.Unix_error _ -> ());
        let out = r.Mcp_core.Proc.output in
        let body = if String.trim out = "" then "(no output)" else out in
        M.text_result
          (Printf.sprintf "exit %d%s\n%s"
             r.Mcp_core.Proc.exit_code
             (if r.Mcp_core.Proc.timed_out then " (TIMEOUT)" else "")
             (String.sub body 0 (min 6000 (String.length body)))));
  }

(* A45: client-side mirror of the acceptance gate's cheap layers, so an
   agent can verify BEFORE declaring done (A43: submissions failed on
   leftover Admitted scaffolding the author forgot to clean). *)
let forbidden_res =
  List.map
    (fun (pat, label) -> (Str.regexp pat, label))
    [ ("\\badmit\\b", "admit"); ("\\bAdmitted\\b", "Admitted");
      ("\\bAxioms?\\b", "Axiom"); ("\\bParameters?\\b", "Parameter");
      ("\\bHypothes[ei]s\\b", "Hypothesis");
      ("\\bVariables?\\b", "Variable") ]

let strip_comments src =
  let b = Buffer.create (String.length src) in
  let n = String.length src in
  let i = ref 0 and depth = ref 0 in
  while !i < n do
    let two = !i + 1 < n in
    if !depth > 0 then begin
      if src.[!i] = '"' then begin
        incr i;
        while !i < n && src.[!i] <> '"' do incr i done;
        incr i
      end
      else if two && src.[!i] = '(' && src.[!i + 1] = '*' then (incr depth; i := !i + 2)
      else if two && src.[!i] = '*' && src.[!i + 1] = ')' then (decr depth; i := !i + 2)
      else incr i
    end
    else if two && src.[!i] = '(' && src.[!i + 1] = '*' then (incr depth; i := !i + 2)
    else begin
      Buffer.add_char b src.[!i];
      incr i
    end
  done;
  Buffer.contents b

let verify_tool : M.tool =
  {
    name = "verify";
    description =
      "Check the workspace AGAINST THE ACCEPTANCE GATE'S rules before you \
       declare the project done: (1) scans every .v file for forbidden \
       tokens (admit/Admitted/Axiom/Parameter/Hypothesis/Variable — these \
       REJECT the submission even if the build passes); (2) runs a clean \
       dune build. Call this before replying DONE and fix everything it \
       reports.";
    input_schema =
      `Assoc [ ("type", `String "object"); ("properties", `Assoc []) ];
    handler =
      (fun _ ->
        let issues = ref [] in
        let rec scan dir =
          match Sys.readdir dir with
          | entries ->
              Array.iter
                (fun e ->
                  let p = Filename.concat dir e in
                  if e = "_build" || (String.length e > 0 && e.[0] = '.') then ()
                  else if Sys.is_directory p then scan p
                  else if Filename.check_suffix e ".v" then begin
                    let ic = open_in_bin p in
                    let txt = really_input_string ic (in_channel_length ic) in
                    close_in ic;
                    let body = strip_comments txt in
                    List.iter
                      (fun (rx, label) ->
                        try
                          ignore (Str.search_forward rx body 0);
                          issues :=
                            Printf.sprintf "%s: forbidden token `%s`"
                              (Filename.basename p) label
                            :: !issues
                        with Not_found -> ())
                      forbidden_res
                  end)
                entries
          | exception Sys_error _ -> ()
        in
        scan (Lazy.force root);
        let lock_path = Filename.concat (Lazy.force root) ".team_build_lock" in
        let fd = Unix.openfile lock_path [ Unix.O_CREAT; Unix.O_WRONLY ] 0o644 in
        Unix.lockf fd Unix.F_LOCK 0;
        let r =
          Mcp_core.Proc.run ~timeout_s:240. ~cwd:(Lazy.force root)
            [| "dune"; "build"; "--root"; "." |]
        in
        (try Unix.lockf fd Unix.F_ULOCK 0; Unix.close fd
         with Unix.Unix_error _ -> ());
        let build_ok = r.Mcp_core.Proc.exit_code = 0 in
        if !issues = [] && build_ok then
          M.text_result "VERIFY OK: build clean, no forbidden tokens. Safe to reply DONE."
        else
          M.text_result
            (Printf.sprintf "VERIFY FAILED — fix before DONE:\n%s%s"
               (String.concat "\n" (List.map (fun x -> "- " ^ x) (List.rev !issues)))
               (if build_ok then ""
                else "\n- dune build FAILS:\n" ^
                     String.sub r.Mcp_core.Proc.output 0
                       (min 2500 (String.length r.Mcp_core.Proc.output)))));
  }

let () = M.run [ write_tool; read_tool; list_tool; build_tool; verify_tool ]
