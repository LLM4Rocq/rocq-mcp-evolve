(* Suite C — scalability / latency bounds (see test/ARCHITECTURE.md).
   Generous, CI-stable bounds; every check exercises a real binary.
     C1 session init < 15 s and step p50 < 250 ms   (session MCP server)
     C2 daemon under load, no deadlock               (8 threads x 10 ops)
     C3 snapshot rollback O(1)-ish                   (rollback{50} < 2 s) *)

module H = Test_helpers.Helpers
module J = Yojson.Safe
module JU = Yojson.Safe.Util

let now () = Unix.gettimeofday ()

(* fixtures *)
let f2 = "Theorem t2 : forall n : nat, n + 0 = n.\n"

let fb =
  "From Stdlib Require Import Reals Psatz.\n\
   Open Scope R_scope.\n\n\
   Theorem tb (x : R) (h : 0 < x) : 0 < x * 2 /\\ 0 < x * x.\n"

(* ---------- local daemon launcher (do NOT touch helpers.ml) ---------- *)

type daemon = { pid : int; sock_path : string }

let short_sock () =
  Printf.sprintf "/tmp/rt%d_%d.sock" (Unix.getpid ()) (Random.int 1000000)

let file_contains path needle =
  try
    let ic = open_in_bin path in
    let n = in_channel_length ic in
    let s = really_input_string ic n in
    close_in ic;
    H.contains s needle
  with _ -> false

let spawn_daemon ~task_file ~workdir ~sock_path : daemon =
  (try Sys.remove sock_path with _ -> ());
  let errfile = Filename.concat workdir "daemon.err" in
  let err_fd =
    Unix.openfile errfile [ Unix.O_WRONLY; Unix.O_CREAT; Unix.O_TRUNC ] 0o644
  in
  let devnull = Unix.openfile "/dev/null" [ Unix.O_RDONLY ] 0 in
  let env =
    [| "PATH=" ^ H.base_path;
       "HOME=" ^ (try Sys.getenv "HOME" with Not_found -> "/tmp");
       "ROCQ_TASK_FILE=" ^ task_file;
       "ROCQ_WORKDIR=" ^ workdir;
       "ROCQ_SOCKET=" ^ sock_path |]
  in
  let pid =
    Unix.create_process_env H.daemon_exe [| H.daemon_exe |] env devnull err_fd
      err_fd
  in
  Unix.close devnull;
  Unix.close err_fd;
  let deadline = now () +. 100. in
  let rec wait_ready () =
    if file_contains errfile "daemon ready" then ()
    else if now () > deadline then failwith "daemon never printed 'daemon ready'"
    else (
      Unix.sleepf 0.2;
      wait_ready ())
  in
  wait_ready ();
  let rec wait_sock k =
    match try Some (H.sock_connect sock_path) with _ -> None with
    | Some c -> H.sock_close c
    | None ->
        if k <= 0 then failwith "daemon socket never accepted"
        else (
          Unix.sleepf 0.5;
          wait_sock (k - 1))
  in
  wait_sock 60;
  { pid; sock_path }

let kill_daemon (d : daemon) =
  (try Unix.kill (-d.pid) Sys.sigkill with _ -> ());
  (try Unix.kill d.pid Sys.sigkill with _ -> ());
  (try ignore (Unix.waitpid [] d.pid) with _ -> ());
  (try Sys.remove d.sock_path with _ -> ())

(* ---------- C1: session init + per-step latency ---------- *)

let c1 () =
  let td = H.tmpdir "perf_c1" in
  H.write_file (Filename.concat td "task.v") f2;
  let env =
    [ ("ROCQ_TASK_FILE", Filename.concat td "task.v"); ("ROCQ_WORKDIR", td) ]
  in
  let t0 = now () in
  let srv = H.spawn_server ~env H.session_exe in
  Fun.protect
    ~finally:(fun () -> H.close srv)
    (fun () ->
      H.initialize srv;
      (* first tool call triggers the lazy prover init + prefix compile *)
      let r0 =
        H.call srv ~name:"step" ~args:(`Assoc [ ("text", `String "intros n.") ])
      in
      let init_dt = now () -. t0 in
      (* content sanity: the prover really ran (guards vacuous timing checks) *)
      H.check (H.contains r0 "sentence(s) committed") "C1 session actually ran";
      H.check (init_dt < 15.) (Printf.sprintf "C1 session init < 15s (%.2fs)" init_dt);
      (* 20 trivial steps, measure per-call round-trip *)
      let n = 20 in
      let times = Array.make n 0. in
      let ok_steps = ref 0 in
      let steps_t0 = now () in
      for i = 0 to n - 1 do
        let a = now () in
        let r =
          H.call srv ~name:"step" ~args:(`Assoc [ ("text", `String "idtac.") ])
        in
        times.(i) <- now () -. a;
        if H.contains r "sentence(s) committed" then incr ok_steps
      done;
      H.check (!ok_steps = n) "C1 all 20 steps committed";
      let steps_total = now () -. steps_t0 in
      let sorted = Array.copy times in
      Array.sort compare sorted;
      let median = (sorted.(n / 2 - 1) +. sorted.(n / 2)) /. 2. in
      H.check (median < 0.250)
        (Printf.sprintf "C1 step p50 < 250ms (%.0fms)" (median *. 1000.));
      H.check (steps_total < 15.)
        (Printf.sprintf "C1 20 steps total < 15s (%.2fs)" steps_total))

(* ---------- C2: daemon under concurrent load, no deadlock ---------- *)

let c2 () =
  let td = H.tmpdir "perf_c2" in
  let task = Filename.concat td "task.v" in
  H.write_file task fb;
  let sock = short_sock () in
  let d = spawn_daemon ~task_file:task ~workdir:td ~sock_path:sock in
  Fun.protect
    ~finally:(fun () -> kill_daemon d)
    (fun () ->
      let n_threads = 8 and n_ops = 10 in
      let total = n_threads * n_ops in
      let oks = Array.make total false in
      let worker t =
        let c = H.sock_connect sock in
        for j = 0 to n_ops - 1 do
          let idx = (t * n_ops) + j in
          let op = if j land 1 = 0 then "state" else "goals" in
          let resp =
            try
              H.sock_rpc c
                [ ("op", `String op);
                  ("agent", `String (Printf.sprintf "L%d" t)) ]
            with _ -> `Null
          in
          oks.(idx) <- JU.member "ok" resp = `Bool true
        done;
        H.sock_close c
      in
      let t0 = now () in
      let threads = Array.init n_threads (fun t -> Thread.create worker t) in
      Array.iter Thread.join threads;
      let dt = now () -. t0 in
      let all_ok = Array.for_all (fun b -> b) oks in
      H.check all_ok
        (Printf.sprintf "C2 all %d responses well-formed ok=true" total);
      H.check (dt < 30.)
        (Printf.sprintf "C2 %d concurrent ops < 30s (%.2fs)" total dt))

(* ---------- C3: snapshot rollback is cheap ---------- *)

let c3 () =
  let td = H.tmpdir "perf_c3" in
  H.write_file (Filename.concat td "task.v") f2;
  let env =
    [ ("ROCQ_TASK_FILE", Filename.concat td "task.v"); ("ROCQ_WORKDIR", td) ]
  in
  let srv = H.spawn_server ~env H.session_exe in
  Fun.protect
    ~finally:(fun () -> H.close srv)
    (fun () ->
      H.initialize srv;
      (* commit 50 sentences via ONE step call (idtac. is a valid no-op) *)
      let text = String.concat " " (List.init 50 (fun _ -> "idtac.")) in
      let r = H.call srv ~name:"step" ~args:(`Assoc [ ("text", `String text) ]) in
      H.check
        (H.contains r "50 sentence(s) committed")
        "C3 committed 50 sentences";
      let t0 = now () in
      let rb = H.call srv ~name:"rollback" ~args:(`Assoc [ ("count", `Int 50) ]) in
      let dt = now () -. t0 in
      H.check (H.contains rb "rolled back 50") "C3 rolled back 50 sentences";
      H.check (dt < 2.)
        (Printf.sprintf "C3 rollback{50} < 2s (%.3fs)" dt))

let () =
  c1 ();
  c2 ();
  c3 ();
  H.summary "suite C (perf)"
