#!/usr/bin/env python3
"""Plain-text REPL for the session server: type tool commands, see the reply.

    python3 scripts/mcp_repl.py                      # interactive, all tools
    python3 scripts/mcp_repl.py --task some/task_prefix.v --tools step,rollback,state,try,auto_close
    printf 'open %s demo\nstep intros.\nauto_close\n' /abs/Demo.v | python3 scripts/mcp_repl.py

Commands (one per line; the rest of the line is the argument):
    open <abs-file> [theorem]        start a session on a file (optionally target a theorem)
    step <sentences>                 run one or more Rocq sentences
    state                            goals + committed proof so far
    try <tac1> ;; <tac2> ;; ...      speculative candidates, best-effort order
    auto_close                       finishing portfolio on the current goal
    rollback [n]                     undo the last n committed sentences (default 1)
    check <whole proof script>       check a complete proof in one call
    build <abs-file>                 whole-file diagnosis
    verify                           dune build at the project root
    raw <tool> <json-args>           any tool with literal JSON arguments
    tools                            list the tools this server exposes
    quit
Options: --exe PATH (default: the built session server), --workdir DIR (ROCQ_WORKDIR),
--task FILE (ROCQ_TASK_FILE, benchmark-style preset), --tools a,b,c (ROCQ_ENABLE_TOOLS),
--env KEY=VAL (repeatable). stderr of the server goes to <workdir>/server.stderr.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXE = REPO / "_build/default/src/session_server/rocq_agent_session.exe"
OPAM_BIN = REPO.parent / "_opam" / "bin"


class Server:
    def __init__(self, exe, env, workdir):
        self.err = open(Path(workdir) / "server.stderr", "w")
        self.p = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.err, text=True, env=env, bufsize=1)
        self.n = 0

    def call(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise SystemExit("server exited (see server.stderr)")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                return msg

    def tool(self, name, args):
        msg = self.call("tools/call", {"name": name, "arguments": args})
        if "error" in msg:
            return "ERROR " + json.dumps(msg["error"])
        r = msg.get("result", {})
        content = r.get("content") or []
        text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
        return text or json.dumps(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(EXE))
    ap.add_argument("--workdir", default="/tmp/rocq_mcp_repl")
    ap.add_argument("--task", default="")
    ap.add_argument("--tools", default="")
    ap.add_argument("--env", action="append", default=[])
    a = ap.parse_args()
    Path(a.workdir).mkdir(parents=True, exist_ok=True)
    env = {"PATH": f"{OPAM_BIN}:{os.environ.get('PATH', '')}", "HOME": os.environ.get("HOME", ""),
           "ROCQ_WORKDIR": a.workdir, "ROCQ_LOG_FILE": str(Path(a.workdir) / "server.jsonl")}
    if a.task:
        env["ROCQ_TASK_FILE"] = str(Path(a.task).resolve())
    if a.tools:
        env["ROCQ_ENABLE_TOOLS"] = a.tools
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v
    s = Server(a.exe, env, a.workdir)
    init = s.call("initialize", {})
    tools = [t["name"] for t in s.call("tools/list", {})["result"]["tools"]]
    interactive = sys.stdin.isatty()
    if interactive:
        print(f"connected: {init['result'].get('serverInfo')}  tools: {', '.join(tools)}")
        print(f"workdir {a.workdir}  (candidate.v and server.jsonl land there). Type a command, 'quit' to exit.")
    while True:
        try:
            line = input("rocq> " if interactive else "")
        except EOFError:
            break
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cmd, _, rest = line.partition(" ")
        rest = rest.strip()
        if cmd == "quit":
            break
        if not interactive:
            print(f"rocq> {line}")
        if cmd == "tools":
            print(", ".join(tools)); continue
        if cmd == "open":
            f, _, thm = rest.partition(" ")
            args = {"file": str(Path(f).resolve())}
            if thm.strip():
                args["theorem"] = thm.strip()
            out = s.tool("open", args)
        elif cmd == "step":
            out = s.tool("step", {"text": rest})
        elif cmd == "state":
            out = s.tool("state", {})
        elif cmd == "try":
            out = s.tool("try", {"candidates": [c.strip() for c in rest.split(";;") if c.strip()]})
        elif cmd == "auto_close":
            out = s.tool("auto_close", {})
        elif cmd == "rollback":
            out = s.tool("rollback", {"count": int(rest or 1)})
        elif cmd == "check":
            out = s.tool("check", {"script": rest})
        elif cmd == "build":
            out = s.tool("build", {"file": str(Path(rest).resolve())})
        elif cmd == "verify":
            out = s.tool("verify", {})
        elif cmd == "raw":
            name, _, js = rest.partition(" ")
            out = s.tool(name, json.loads(js or "{}"))
        else:
            out = f"unknown command '{cmd}' (see --help)"
        print(out)
        print()
    s.p.stdin.close()
    s.p.wait(timeout=10)


if __name__ == "__main__":
    main()
