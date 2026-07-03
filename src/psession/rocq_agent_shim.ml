(* MCP stdio shim for the shared-proof daemon: each policy agent runs one shim
   (spawned by the claude CLI); every tool call is forwarded as one line-JSON
   request to $ROCQ_SOCKET with this agent's $ROCQ_AGENT_ID attached. The
   daemon holds all proof state; the shim is stateless plumbing. *)

module M = Mcp_core.Mcp_server
module J = Yojson.Safe
module JU = Yojson.Safe.Util

let agent_id =
  lazy (match Sys.getenv_opt "ROCQ_AGENT_ID" with Some a when a <> "" -> a | _ -> "anon")

let sock =
  lazy
    (let path =
       match Sys.getenv_opt "ROCQ_SOCKET" with
       | Some p when p <> "" -> p
       | _ -> failwith "ROCQ_SOCKET not set"
     in
     let fd = Unix.socket Unix.PF_UNIX Unix.SOCK_STREAM 0 in
     Unix.connect fd (Unix.ADDR_UNIX path);
     (fd, Unix.in_channel_of_descr fd))

let rpc (fields : (string * J.t) list) : J.t =
  let fd, ic = Lazy.force sock in
  let msg =
    `Assoc (("agent", `String (Lazy.force agent_id)) :: fields)
  in
  let line = J.to_string msg ^ "\n" in
  ignore (Unix.write_substring fd line 0 (String.length line));
  J.from_string (input_line ic)

let text_of (resp : J.t) =
  match JU.member "text" resp with
  | `String s -> s
  | _ -> J.to_string resp

let fwd ?(extra = fun (_ : J.t) -> []) op (args_of : J.t -> (string * J.t) list)
    : J.t -> M.tool_result =
 fun args ->
  match rpc (("op", `String op) :: args_of args) with
  | resp ->
      let ok = JU.member "ok" resp = `Bool true in
      M.text_result ~is_error:(not ok) (text_of resp) ~log:(extra resp)
  | exception e ->
      M.text_result ~is_error:true ("daemon unreachable: " ^ Printexc.to_string e)

let obj props required =
  `Assoc
    [ ("type", `String "object");
      ("properties", `Assoc props);
      ("required", `List (List.map (fun r -> `String r) required)) ]

let str_prop desc = `Assoc [ ("type", `String "string"); ("description", `String desc) ]
let int_prop desc = `Assoc [ ("type", `String "integer"); ("description", `String desc) ]

let tools : M.tool list =
  [
    { name = "state";
      description = "Show the goals you are currently working on (your focused subgoal, or the whole proof if unfocused).";
      input_schema = obj [] [];
      handler = fwd "state" (fun _ -> []) };
    { name = "goals";
      description = "List the open subgoals of the shared proof with their ids and owners (another agent may already own one).";
      input_schema = obj [] [];
      handler =
        (fun _args ->
          match rpc [ ("op", `String "goals") ] with
          | resp ->
              let lines =
                match JU.member "goals" resp with
                | `List l ->
                    List.map
                      (fun g ->
                        Printf.sprintf "[%d]%s %s"
                          (JU.member "id" g |> JU.to_int)
                          (match JU.member "owner" g with
                           | `String o -> " (owned by " ^ o ^ ")"
                           | _ -> "")
                          (JU.member "concl" g |> JU.to_string))
                      l
                | _ -> [ J.to_string resp ]
              in
              M.text_result
                (if lines = [] then "no open goals" else String.concat "\n" lines)
          | exception e ->
              M.text_result ~is_error:true ("daemon unreachable: " ^ Printexc.to_string e)) };
    { name = "focus";
      description = "Claim subgoal <goal> (from goals) as yours and start working on it. Your step/try/auto_close then apply only to it; when you close it, it is merged into the shared proof automatically.";
      input_schema = obj [ ("goal", int_prop "subgoal id from goals") ] [ "goal" ];
      handler = fwd "focus" (fun a -> [ ("goal", JU.member "goal" a) ]) };
    { name = "step";
      description = "Execute Rocq sentences on your focused subgoal (or the main proof if unfocused). Successes commit permanently; on failure you get the error and the state after the last success. Queries (Search/Check) work too.";
      input_schema = obj [ ("text", str_prop "Rocq sentences") ] [ "text" ];
      handler = fwd "step" (fun a -> [ ("text", JU.member "text" a) ]) };
    { name = "try";
      description = "Speculatively test up to 8 candidate tactic scripts against your current goal in one call; nothing commits — follow up with step.";
      input_schema =
        obj
          [ ("candidates",
             `Assoc
               [ ("type", `String "array");
                 ("items", `Assoc [ ("type", `String "string") ]) ]) ]
          [ "candidates" ];
      handler = fwd "try" (fun a -> [ ("candidates", JU.member "candidates" a) ]) };
    { name = "auto_close";
      description = "Run the standard finisher portfolio (lia/lra/nra/nia/field_simp variants/ring/psatz/auto) on your current goal; a success commits automatically. Call it first on every goal.";
      input_schema = obj [] [];
      handler = fwd "auto_close" (fun _ -> []) };
  ]

let () = M.run tools
