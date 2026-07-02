(* Subprocess execution with hard timeout and combined-output capture.
   Used by every tool config that shells out to the prover, so timeout and
   capture semantics are identical across experimental conditions. *)

type result = {
  exit_code : int; (* -1 if killed *)
  timed_out : bool;
  output : string; (* stdout+stderr interleaved *)
  dur_s : float;
}

let max_output_bytes = 200_000

let read_capped path =
  match open_in_bin path with
  | exception Sys_error _ -> ""
  | ic ->
      let len = in_channel_length ic in
      let n = min len max_output_bytes in
      let s = really_input_string ic n in
      close_in ic;
      if len > n then s ^ Printf.sprintf "\n[... output truncated: %d of %d bytes shown]" n len
      else s

(* Kill pid, its process group, and all descendants. `rocqworker` (spawned by
   `rocq compile`) moves itself into its own process group, so a plain group
   kill leaks it — walk children via pgrep -P before killing the parent. *)
let kill_tree pid =
  let read_children p =
    let ic = Unix.open_process_in (Printf.sprintf "pgrep -P %d 2>/dev/null" p) in
    let rec go acc =
      match input_line ic with
      | l -> go ((try [ int_of_string (String.trim l) ] with _ -> []) @ acc)
      | exception End_of_file -> acc
    in
    let cs = go [] in
    ignore (Unix.close_process_in ic);
    cs
  in
  let rec descendants p =
    let cs = read_children p in
    List.concat_map (fun c -> c :: descendants c) cs
  in
  let ds = descendants pid in
  List.iter (fun p -> try Unix.kill p Sys.sigkill with _ -> ()) ds;
  (try Unix.kill (-pid) Sys.sigkill with _ -> ());
  (try Unix.kill pid Sys.sigkill with _ -> ())

let run ?(timeout_s = 60.) ?(cwd : string option) (argv : string array) : result =
  let out_path = Filename.temp_file "rocq_proc_" ".out" in
  let out_fd = Unix.openfile out_path [ Unix.O_WRONLY; Unix.O_TRUNC ] 0o600 in
  let devnull = Unix.openfile "/dev/null" [ Unix.O_RDONLY ] 0 in
  let t0 = Unix.gettimeofday () in
  let pid = Unix.fork () in
  if pid = 0 then begin
    (* child: own process group so the whole tree can be killed *)
    ignore (Unix.setsid ());
    (match cwd with Some d -> (try Unix.chdir d with _ -> ()) | None -> ());
    Unix.dup2 devnull Unix.stdin;
    Unix.dup2 out_fd Unix.stdout;
    Unix.dup2 out_fd Unix.stderr;
    (try Unix.execvp argv.(0) argv
     with _ ->
       prerr_string ("exec failed: " ^ argv.(0));
       exit 127)
  end;
  Unix.close out_fd;
  Unix.close devnull;
  let deadline = t0 +. timeout_s in
  let rec wait () =
    match Unix.waitpid [ Unix.WNOHANG ] pid with
    | 0, _ ->
        if Unix.gettimeofday () > deadline then begin
          kill_tree pid;
          ignore (Unix.waitpid [] pid);
          (true, -1)
        end
        else begin
          ignore (Unix.select [] [] [] 0.02);
          wait ()
        end
    | _, Unix.WEXITED c -> (false, c)
    | _, (Unix.WSIGNALED _ | Unix.WSTOPPED _) -> (false, -1)
  in
  let timed_out, exit_code = wait () in
  let dur_s = Unix.gettimeofday () -. t0 in
  let output = read_capped out_path in
  (try Sys.remove out_path with _ -> ());
  { exit_code; timed_out; output; dur_s }
