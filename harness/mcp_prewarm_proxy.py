#!/usr/bin/env python3
"""Instant-handshake MCP proxy (fair-integration fix, REPORT SOTA section).

The claude CLI only exposes an MCP server's tools from the agent's first
turn if the server completes the handshake within a short synchronous
window. Our in-process OCaml servers answer in milliseconds; rocq-mcp's
Python stack takes ~0.5-1 s, so 97 % of comparison attempts started with
its tools invisible (comparison retracted).

This proxy answers the handshake INSTANTLY from a captured cache
(harness/rocq_mcp_handshake_cache.json) while the real server warms up
behind it; tool calls are forwarded verbatim (queued until the child is
ready). Transparent: same tools, same behavior, only the startup race
removed.

Usage (as the MCP server command):
    python3 -S mcp_prewarm_proxy.py <real-server-command> [args...]
"""

import json
import os
import subprocess
import sys
import threading

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "rocq_mcp_handshake_cache.json")
PROXY_INIT_ID = "__proxy_init__"
PROXY_TOOLS_ID = "__proxy_tools__"


def out(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main():
    with open(CACHE) as f:
        cache = json.load(f)

    child = subprocess.Popen(
        sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=sys.stderr, text=True, bufsize=1)

    child_ready = threading.Event()
    child_lock = threading.Lock()

    def to_child(m):
        with child_lock:
            child.stdin.write(json.dumps(m) + "\n")
            child.stdin.flush()

    # proxy's own handshake with the child, started immediately
    to_child({"jsonrpc": "2.0", "id": PROXY_INIT_ID, "method": "initialize",
              "params": {"protocolVersion":
                         cache["initialize"].get("protocolVersion",
                                                 "2025-11-25"),
                         "capabilities": {},
                         "clientInfo": {"name": "prewarm-proxy",
                                        "version": "1"}}})

    def pump_child():
        for line in child.stdout:
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("id") == PROXY_INIT_ID:
                to_child({"jsonrpc": "2.0",
                          "method": "notifications/initialized"})
                child_ready.set()
                continue
            if m.get("id") == PROXY_TOOLS_ID:
                continue
            out(m)  # responses + notifications flow straight through

    threading.Thread(target=pump_child, daemon=True).start()

    for line in sys.stdin:
        try:
            m = json.loads(line)
        except json.JSONDecodeError:
            continue
        meth = m.get("method", "")
        if meth == "initialize":
            res = dict(cache["initialize"])
            req_pv = (m.get("params") or {}).get("protocolVersion")
            if req_pv:
                res["protocolVersion"] = req_pv
            out({"jsonrpc": "2.0", "id": m.get("id"), "result": res})
        elif meth == "notifications/initialized":
            pass  # proxy already initialized the child
        elif meth == "tools/list":
            out({"jsonrpc": "2.0", "id": m.get("id"),
                 "result": cache["tools"]})
        elif meth in ("prompts/list", "resources/list"):
            key = "prompts" if "prompts" in meth else "resources"
            out({"jsonrpc": "2.0", "id": m.get("id"), "result": {key: []}})
        else:
            child_ready.wait(timeout=60)
            to_child(m)

    child.kill()


if __name__ == "__main__":
    main()
