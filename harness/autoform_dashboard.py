#!/usr/bin/env python3
"""Phase-2 dashboard: evaluation & evolution of rocq-mcp-evolve on
autoformalization tasks.

    python3 harness/autoform_dashboard.py   # writes logs/autoform_dashboard.html

HEADLINE = the current arena only (af3, A63: no system prompt, wall-only
900 s budget, 5 tasks x 4 reps) — control, shipped server, and one row per
evolution rung. Every older run (w2 guided era, af2 40-turn arena) is
confounded or superseded and appears ONLY in the all-runs history table,
each with an explicit comment saying why.
"""

import html
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common

LOGS = common.LOGS / "autoform"

# tasks (clean names; w2-era runs logged them as w2_* — normalized on read)
TASK_IDS = ["frugal", "gauges", "ledger", "prodauto", "triadic"]


def _norm_task(t):
    return t[3:] if t.startswith("w2_") else t


# ---- current arena (A63): the only arms reported as results ---------------
CONTROL = "af3_base"
CURRENT = [
    (CONTROL, "baseline (files + dune, no MCP)",
     "the control every rung is judged against"),
    ("af3_evolve", "+ rocq-mcp-evolve (shipped)",
     "the server as shipped at the arena freeze (incl. relative paths A48, "
     "import-echo A59)"),
    ("af3_sota", "+ rocq-mcp (SOTA sibling)",
     "reference arm under the identical fair protocol — +2 over baseline "
     "(within noise, A75); evolve keeps ~2x cost/solved, latency, and "
     "prodauto (A70→A75)"),
]
# evolution rungs auto-discovered: af3_evolve_r1, _r2, ... (one measured
# change each; keep/revert by the frozen |delta solved| >= 3 rule)
RUNG_LABELS = {
    "af3_evolve_r1": ("R1: scaffold visibility in build{} — REVERTED",
                      "build{} warned about admit/Admitted/Abort left in the "
                      "file (A64) — no signal (corrected 15 vs 14), warning reached "
                      "only 6/20 attempts; reverted"),
    "af3_evolve_c3": ("C3: goal-diff rendering by default — REVERTED",
                      "accuracy flat but cost/solved +27%, input tokens "
                      "+33%: compact replies made the model buy the elided "
                      "context back with extra round-trips (A69 verdict — "
                      "density per exchange beats tokens per reply)"),
    "af3_evolve_r3": ("R3: open runs the finishers automatically — REVERTED",
                      "best point estimate of the arc but +1 vs the corrected "
                      "shipped arm — below the keep bar; mechanism: 1 of 70 fused "
                      "opens closed a goal — automation at the wrong time "
                      "(A65 verdict)"),
}

# ---- history: every other run, with an explicit why-not-headline comment --
HISTORY_COMMENTS = {
    "w2_base_sonnet":
        "guided era: per-arm system prompts + 40-turn arena — arms are not "
        "prompt-comparable across treatments; superseded by af3",
    "w2_prover_sonnet":
        "guided evolve arm (recipe system prompt); its 7/8 is REAL but "
        "guided — the prompt differs from base's (A54); 40-turn arena",
    "w2_verify_sonnet":
        "RETRACTED arm: bundled Admitted-scaffold prompt under the 40-turn "
        "cap caused the losses, not the tools (A54)",
    "w2_team_sonnet":
        "multi-agent probe, 1 rep: teams add no value once solo is strong "
        "(A56); orchestration stays harness scaffolding",
    "w2_sota_unfair":
        "SOTA sibling + generic tool-list prompt while the evolve arm had a "
        "tuned recipe prompt — unfair pairing, archived (A58)",
    "w2_sota_sonnet":
        "SOTA sibling + tuned recipe prompt (prompt-asymmetry hypothesis "
        "REFUTED by this run, A58b); 40-turn arena",
    "af2_base":
        "fair no-prompt protocol BUT 40-turn cap = 40-tool-call cap (0% "
        "parallel calls, A62b) — structurally punishes tool-rich arms; "
        "superseded by the af3 wall-only arena",
    "af2_evolve":
        "same 40-turn artifact: 17/20 attempts guillotined at the cap while "
        "the baseline was wall-bound (A62); superseded by af3",
    "af2_sota":
        "SOTA sibling under the af2 arena (20/20 turn-capped): -9 vs the "
        "corrected base there (raw -7 pre-A75) — the fair wall-only arena "
        "moved it to +2; the af2 number describes the arena, not the "
        "interface (A62/A70/A75)",
    "af2_smoke_evolve":
        "protocol smoke (1 attempt), excluded from analysis (A60 rule 7)",
    "af2_smoke_sota":
        "protocol smoke (1 attempt), excluded from analysis (A60 rule 7)",
    "op_base": "opus tier, directional n=10 (A73): baseline collapses 3/10",
    "op_evolve": "opus tier (A73): 6/10 — doubles the collapsed baseline",
    "op_sota": "opus tier (A73): 6/10 — ties evolve at the frontier",
    "mst_base": "mistral-medium: 0/20, below the Rocq syntax floor (A72)",
    "mst_evolve": "mistral-medium: 0/20 despite heavy tool use (A72)",
    "mst_probe_magistral":
        "magistral: 0/5, zero tool calls — plans, never acts (A72b)",
    "w2_prover2_sonnet":
        "guided-era secondary prover arm; superseded with the w2 family",
}

LAYERS = {0: "forb", 1: "build", 2: "probe", 3: "audit", 4: "OK"}
LAYER_DESC = {
    0: "forbidden token (leftover admit/Admitted/... — refused even if it builds)",
    1: "dune build fails", 2: "builds but probes reject it",
    3: "probes pass but unexpected axioms", 4: "SOLVED"}
LCOL = {0: "#d03b3b", 1: "#d08b3b", 2: "#c9b93a", 3: "#7ab648", 4: "#1baf7a"}

CSS = """
:root { color-scheme: light dark; }
body { margin:0 auto; padding:24px; max-width:960px; background:#f9f9f7; color:#0b0b0b;
  font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif; }
@media (prefers-color-scheme: dark) { body { background:#0d0d0d; color:#fff; } }
h1 { font-size:20px; margin:0 0 2px; } h2 { font-size:15px; margin:26px 0 6px; }
.caption { color:#898781; font-size:12px; margin:0 0 10px; max-width:840px; }
.card { background:rgba(127,127,127,0.06); border:1px solid rgba(127,127,127,0.2);
  border-radius:10px; padding:14px 16px; }
table { border-collapse:collapse; font-size:12.5px; width:100%; }
th { text-align:left; color:#898781; font-weight:600; }
th,td { padding:5px 10px 5px 0; border-bottom:1px solid rgba(127,127,127,0.15); }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.pill { display:inline-block; border-radius:4px; padding:0 6px; color:#fff;
  font-size:11px; font-weight:600; }
.up { color:#1baf7a; font-weight:600; } .down { color:#d03b3b; font-weight:600; }
.flat { color:#898781; }
.hist { color:#898781; font-size:12px; }
"""


def esc(s):
    return html.escape(str(s))


# cache-aware token prices (claude-sonnet-5), to recover cost for attempts
# killed at the wall — those leave no result event so results.jsonl records
# cost=None even when the attempt SOLVED (grading is on the workspace).
_RIN, _ROUT, _RCR, _RCW = 3e-6, 15e-6, 0.3e-6, 3.75e-6


def _recover_cost(run, task, rep):
    tp = LOGS / run / "attempts" / f"{task}__rep{rep}" / "transcript.jsonl"
    if not tp.exists():
        return 0.0
    tot = 0.0
    for line in tp.read_text(errors="replace").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "result" and e.get("total_cost_usd") is not None:
            return e["total_cost_usd"]
        if e.get("type") == "assistant":
            u = e.get("message", {}).get("usage", {})
            tot += (u.get("input_tokens", 0) * _RIN
                    + u.get("output_tokens", 0) * _ROUT
                    + u.get("cache_read_input_tokens", 0) * _RCR
                    + u.get("cache_creation_input_tokens", 0) * _RCW)
    return tot


def rows_of(run):
    rows = common.read_jsonl(LOGS / run / "results.jsonl")
    # A75: gate-fix regrades override raw rows (originals preserved on disk)
    over = {(r["task"], r["rep"]): r
            for r in common.read_jsonl(LOGS / run / "regrades.jsonl")}
    rows = [over.get((r["task"], r["rep"]), r) for r in rows]
    for r in rows:
        if r.get("total_cost_usd") is None:
            r["total_cost_usd"] = _recover_cost(run, r["task"], r["rep"])
    return rows


def by_task(run):
    rows = rows_of(run)
    return {t: [r for r in rows if _norm_task(r["task"]) == t] for t in TASK_IDS}


def metrics(rows):
    if not rows:
        return None
    n = len(rows)
    s = sum(1 for r in rows if r["solved"])
    cost = sum(r.get("total_cost_usd") or 0 for r in rows)
    solved_rows = [r for r in rows if r["solved"]]
    return {"acc": s / n, "solved": s, "n": n,
            "cps": (cost / s) if s else None,
            "wall": sum(r.get("wall_s") or 0 for r in rows) / n,
            "lat": (sum(r["wall_s"] for r in solved_rows) / s) if s else None,
            "kills": sum(1 for r in rows if r.get("num_turns") is None),
            "cost": cost}


def agg(run):
    return metrics([r for r in rows_of(run) if _norm_task(r["task"]) in TASK_IDS])


def delta(b, e, up_good, fmt):
    if b is None or e is None:
        return f'{fmt(b) if b is not None else "–"} → ' \
               f'<b>{fmt(e) if e is not None else "–"}</b>'
    if b == 0:
        return f'{fmt(b)} → <b>{fmt(e)}</b>'
    pct = (e - b) / b * 100
    if abs(pct) < 1:
        return f'{fmt(e)} <span class="flat">=</span>'
    good = (pct >= 0) if up_good else (pct <= 0)
    cls = "up" if good else "down"
    arrow = "▲" if pct >= 0 else "▼"
    return f'<b>{fmt(e)}</b> <span class="{cls}">{arrow}{abs(pct):.0f}%</span>'


def headline_table():
    """Current-arena headline table + arms list. Extracted so the combined
    results page (dashboard.py) embeds the SAME rendering — no duplication."""
    fcost = lambda v: f"${v:.2f}" if v is not None else "–"
    fwall = lambda v: f"{v:.0f}s" if v is not None else "–"
    rungs = [r for r in ("af3_evolve_r1", "af3_evolve_r3", "af3_evolve_c3")
             if (LOGS / r / "results.jsonl").exists()]
    arms = list(CURRENT) + [
        (r, *RUNG_LABELS.get(r, (r, "evolution rung"))) for r in rungs]
    b = agg(CONTROL)
    head_rows = []
    for run, label, note in arms:
        m = agg(run)
        if m is None:
            continue
        flight = "" if m["n"] >= 20 else \
            f' <span class="flat">· {m["n"]}/20 in flight</span>'
        if run == CONTROL or b is None:
            cells = (f"<td class=num>{m['solved']}/{m['n']}</td>"
                     f"<td class=num>{fcost(m['cps'])}</td>"
                     f"<td class=num>{fwall(m['lat'])}</td>"
                     f"<td class=num>{m['kills']}/{m['n']}</td>")
        else:
            sig = ("criterion met" if abs(m["solved"] - b["solved"]) >= 3
                   and m["n"] >= 20 else "within noise" if m["n"] >= 20
                   else "…")
            cells = (f"<td class=num>{m['solved']}/{m['n']} "
                     f"<span class=flat>({b['solved']}→{m['solved']}, {sig})</span></td>"
                     f"<td class=num>{delta(b['cps'], m['cps'], False, fcost)}</td>"
                     f"<td class=num>{delta(b['lat'], m['lat'], False, fwall)}</td>"
                     f"<td class=num>{m['kills']}/{m['n']}</td>")
        head_rows.append(
            f"<tr><td><b>{esc(label)}</b>{flight}<br>"
            f"<span class=hist>{esc(note)}</span></td>{cells}</tr>")
    return ("<table><tr><th>arm (current arena)</th><th class=num>solved</th>"
            "<th class=num>$ / solved</th><th class=num>latency (solved)</th>"
            "<th class=num>wall-killed</th></tr>"
            + "".join(head_rows) + "</table>"), arms


def build():
    fcost = lambda v: f"${v:.2f}" if v is not None else "–"
    fwall = lambda v: f"{v:.0f}s" if v is not None else "–"
    headline, arms = headline_table()

    # ---- pill grid for current arms ------------------------------------
    data = {a[0]: by_task(a[0]) for a in arms}
    ghead = ("<tr><th>task</th>"
             + "".join(f"<th>{esc(a[1])}</th>" for a in arms) + "</tr>")
    grows = []
    for tid in TASK_IDS:
        tds = [f"<td><b>{esc(tid)}</b></td>"]
        for a in arms:
            cells = data[a[0]].get(tid, [])
            if not cells:
                tds.append("<td>–</td>")
                continue
            tds.append("<td>" + "".join(
                f'<span class="pill" style="background:{LCOL[r["layer"]]}" '
                f'title="{esc(LAYERS[r["layer"]])} = {esc(LAYER_DESC[r["layer"]])} '
                f'| rep{r["rep"]}: {esc(r["reason"])} · {r["num_turns"]} turns · '
                f'${(r["total_cost_usd"] or 0):.2f}">{LAYERS[r["layer"]]}</span> '
                for r in sorted(cells, key=lambda x: x["rep"])) + "</td>")
        grows.append("<tr>" + "".join(tds) + "</tr>")
    grid = f"<table>{ghead}{''.join(grows)}</table>"

    # ---- all runs (history) --------------------------------------------
    hist_rows = []
    for p in sorted(LOGS.iterdir()):
        if not (p / "results.jsonl").exists():
            continue
        run = p.name
        m = agg(run)
        if m is None:
            continue
        if run in {a[0] for a in arms}:
            comment = "CURRENT ARENA — headline above"
        else:
            comment = HISTORY_COMMENTS.get(
                run, "unlabeled run — treat with suspicion")
        hist_rows.append(
            f"<tr><td>{esc(run)}</td>"
            f"<td class=num>{m['solved']}/{m['n']}</td>"
            f"<td class=num>{fcost(m['cps'])}</td>"
            f"<td class=num>{fwall(m['wall'])}</td>"
            f"<td class=hist>{esc(comment)}</td></tr>")
    history = ("<table><tr><th>run</th><th class=num>solved</th>"
               "<th class=num>$ / solved</th><th class=num>wall/att</th>"
               "<th>status / why not headline</th></tr>"
               + "".join(hist_rows) + "</table>")

    updated = time.strftime("%F %T")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>rocq-mcp-evolve — autoformalization evaluation & evolution</title>
<style>{CSS}</style></head><body>
<h1>rocq-mcp-evolve on autoformalization — evaluation &amp; evolution</h1>
<p class="caption">generated {updated} · Current arena (A63): NO system
prompt (servers documented only by their own shipped READMEs inside an
identical task prompt), wall-only budget (900 s; max_turns is a safety-only
200), 5 novel contamination-controlled tasks × 4 reps, sonnet. A task is
SOLVED only if a fresh isolated dune build + open-book probes + assumption
audit + forbidden-token scan all pass — no tool output is ever trusted.
Decision rule, frozen before data: |Δ solved| ≥ 3 vs control = signal.</p>

<h2>Current arena — control, shipped server, evolution rungs</h2>
<div class="card">{headline}</div>

<h2>Detail — task × arm (one pill per rep, hover for meaning)</h2>
<p class="caption">Layers, worst→best: forb (leftover admit) &lt; build
(dune fails) &lt; probe (probes reject) &lt; audit (stray axioms) &lt; OK
(solved).</p>
<div class="card">{grid}</div>

<h2>Findings so far</h2>
<div class="card"><ol style="margin:4px 0 4px 18px; padding:0; font-size:13px; line-height:1.55">
<li><b>The 40-turn arena was a tool-call cap in disguise</b>: sonnet issues
exactly one tool call per turn (zero multi-call turns across 2,109 audited messages, A62b), so
the old cap guillotined tool-rich arms at ~half the baseline's wallclock.
Under the wall-only arena the unguided prover tools BEAT baseline:
10/20 → 14/20 corrected (+4, criterion met; pooled 4-arm replication
p=0.006), at lower wall (A63/A75/A79).</li>
<li><b>The hardest-task pattern replicates a third time</b>: prodauto
(6 files) 0/4 baseline → 3/4 with the tools — interface value concentrates
where the plain build loop fails outright.</li>
<li><b>Guidance-conditionality resolved</b>: the af2 null (corrected: −4)
was substantially the arena artifact, not proof the tools only work when
prompted. Steering still matters (scaffold/turn-economy habits), which is
what the evolution rungs attack — one measured change each.</li>
<li><b>The interface CLASS wins under the fair arena</b>: the SOTA
sibling, which lost under every turn-capped arena (2/8, 1/8, 2/20), scores
12/20 under wall-only budgets — +2 over the corrected baseline (within
noise, A75) and a statistical tie with evolve on accuracy. All prior "SOTA hurts" headlines were the
same arena artifact that nulled evolve in af2. Evolve's surviving edges:
−49% cost/solved (corrected), solved-only latency, and prodauto 3/4
vs 0/4 at sonnet (A70/A75).</li>
<li><b>triadic is a wall</b>: 0 solves in 51 attempts across every arm,
arena, tier, and model family — kept as the discriminator.</li>
</ol></div>

<h2>All runs — full history (superseded / confounded arms kept for the record)</h2>
<p class="caption">Every run on the current 5-task benchmark (wave-1-pilot runs used a
different, discarded task set — see the chronology in docs/AUTOFORM.md),
including the broken and retracted ones — this project keeps its retractions. The comment says
explicitly why a run is not in the headline. Costs are transcript-recovered
where attempts were killed at the wall.</p>
<div class="card">{history}</div>

<h2>Deferred repairs &amp; open items (explicitly off the results-critical path)</h2>
<p class="caption">Per A84/A84b: quota-poisoning repairs that do NOT feed
any reported table are deferred — run only if time and tokens remain.</p>
<div class="card"><table>
<tr><th>item</th><th>scope</th><th>report impact</th><th>status</th></tr>
<tr><td>universal_dev60 repair</td><td class=num>14/240 slots</td>
<td>dev headline table (haiku evolve row) — repair can only raise it</td>
<td><b>REQUIRED — queued post-chain; lockstep update rule A84e</b></td></tr>
<tr><td>baseline_fable_dev60 repair</td><td class=num>1/60 slots</td>
<td>none (annex)</td><td class=hist>OPTIONAL — if time/tokens</td></tr>
<tr><td>team_decomposable repair</td><td class=num>29/176 slots</td>
<td>none (phase-1 REPORT team claims flagged)</td>
<td class=hist>OPTIONAL — if time/tokens</td></tr>
<tr><td>opus miniF2F trio</td><td class=num>3 arms</td>
<td>none (scope reframed, A81)</td>
<td class=hist>DEFERRED pre-data</td></tr>
<tr><td>reciprocal eval (evolve under sibling harness)</td><td class=num>—</td>
<td>future work</td><td class=hist>FUTURE</td></tr>
</table></div>

<p class="caption">Anti-gaming gate: harness/autoform_gate.py. Dataset:
data/autoform/ (5 tasks, gate-validated references, novel framings).
Decision trail: docs/ASSUMPTIONS.md A39–A64+, story: docs/AUTOFORM.md.
Sonnet arms are small-N; the ±3 rule is the resolution limit.</p>
</body></html>"""


if __name__ == "__main__":
    out = common.LOGS / "autoform_dashboard.html"
    out.write_text(build())
    print(f"wrote {out}")
