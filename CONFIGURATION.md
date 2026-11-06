# MCP configuration

The server communicates over stdio. Set environment variables in your MCP client and restart the server after changing them.

```json
{
  "mcpServers": {
    "rocq": {
      "command": "rocq-mcp-evolve",
      "env": {
        "ROCQ_PROJECT_ROOT": "/absolute/path/to/project",
        "ROCQ_STEP_TIMEOUT": "20",
        "ROCQ_RENDER": "compact"
      }
    }
  }
}
```

For Nix, run `nix build` and set `command` to the absolute path of `result/bin/rocq-mcp-evolve`.

## Timeouts

Timeouts are in seconds and apply per sentence. Use positive, finite values.

| Variable | Default | Applies to |
| --- | --- | --- |
| `ROCQ_STEP_TIMEOUT` | 10 | Sentences submitted through `step` and `check` |
| `ROCQ_QED_TIMEOUT` | 60 | Closing proofs |
| `ROCQ_TRY_TIMEOUT` | 5 | Sentences in speculative candidates |
| `ROCQ_AUTO_TIMEOUT` | 2 | Standard automation candidates |

Import loading, file builds and project verification have separate fixed limits. Longer automation candidates use a fixed five-second limit.

## Projects and tools

Build the project before opening its files. `ROCQ_PROJECT_ROOT` resolves relative file paths. The server discovers load paths from `_CoqProject`, `_RocqProject` or `dune-project`. To override discovery, set `ROCQ_INIT_ARGS` to newline-separated Rocq arguments, for example `-Q\n/absolute/path/to/theories\nMyProject`. Load paths initialize once per server process.

`ROCQ_ENABLE_TOOLS` replaces the enabled tool list with comma-separated names, for example `open,step,state,rollback`. Set `ROCQ_PRELOAD=0` to disable automatic loading of Lia, Lra and Psatz.

## States and printing

Each server process keeps one active proof session in memory. `state` shows all goals and the committed proof. `rollback` restores earlier committed sentences. There are no named checkpoints, redo or persistent states.

Goal rendering is full by default. `ROCQ_RENDER=compact` shortens ordinary responses, while `state` still shows full goals. Rocq printing commands such as `Set Printing All.` can be submitted through `step` and undone through `rollback`.
