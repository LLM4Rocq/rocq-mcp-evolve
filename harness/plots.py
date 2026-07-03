#!/usr/bin/env python3
"""Static report figures (docs/figures/*.svg), reusing the dashboard's
validated chart builders so report and dashboard stay visually consistent.

    python3 harness/plots.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import dashboard as db
from report import bucket_stats

FIGDIR = common.REPO / "docs" / "figures"

# Static figures must not depend on prefers-color-scheme: resolve the CSS
# variables to the validated light-mode palette values.
LIGHT_VARS = {
    "var(--s-easy)": "#2a78d6", "var(--s-medium)": "#1baf7a", "var(--s-hard)": "#eda100",
    "var(--c-baseline)": "#4a3aa7", "var(--c-winner)": "#eb6834",
    "var(--surface-1)": "#fcfcfb", "var(--ink-1)": "#0b0b0b", "var(--ink-2)": "#52514e",
    "var(--ink-3)": "#898781", "var(--grid)": "#e1e0d9", "var(--axis)": "#c3c2b7",
}

CSS = """<style>
text { fill:#52514e; font:11px system-ui,-apple-system,'Segoe UI',sans-serif; }
.tick { fill:#898781; font-variant-numeric:tabular-nums; }
.vlab { fill:#0b0b0b; font-weight:600; }
.grid { stroke:#e1e0d9; stroke-width:1; }
.axis { stroke:#c3c2b7; stroke-width:1; }
</style>"""


def resolve(svg: str) -> str:
    for k, v in LIGHT_VARS.items():
        svg = svg.replace(k, v)
    # inject style + white surface behind the plot
    return svg.replace(">", ">" + CSS + '<rect width="100%" height="100%" fill="#fcfcfb"/>', 1)


def main():
    FIGDIR.mkdir(parents=True, exist_ok=True)
    runs = db.load_runs()
    ladder = db.ladder_runs(runs)
    stats_by_cfg = {}
    for rid, meta, rows in ladder:
        cfg = rows[0].get("config_id", rid)
        stats_by_cfg[cfg] = bucket_stats(rows)

    (FIGDIR / "ladder_pass1.svg").write_text(resolve(db.ladder_chart(stats_by_cfg)))

    minis = {
        "efficiency_tokens_out.svg": ("output tokens / attempt", "tokens_out_mean", lambda v: f"{v/1000:.1f}k"),
        "efficiency_cost.svg": ("cost $ / attempt", "cost_usd_mean", lambda v: f"{v:.3f}"),
        "efficiency_wall.svg": ("wall s / attempt", "wall_s_mean", lambda v: f"{v:.0f}"),
    }
    for fname, (title, key, fmt) in minis.items():
        svg = db.mini_line(title, stats_by_cfg, key, fmt)
        if svg:
            (FIGDIR / fname).write_text(resolve(svg))

    sweeps = db.load_sweeps()
    if sweeps:
        for fname, (title, key, fmt) in {
            "sweep_throughput.svg": ("attempts / hour", "attempts_per_hour", lambda v: f"{v:.0f}"),
            "sweep_wall.svg": ("wall s / attempt", "wall_s_mean", lambda v: f"{v:.0f}"),
            "sweep_rss.svg": ("peak RSS (MB)", "peak_rss_mb", lambda v: f"{v:.0f}"),
        }.items():
            (FIGDIR / fname).write_text(resolve(db.sweep_mini(title, sweeps, key, fmt)))
    print(f"wrote {len(list(FIGDIR.glob('*.svg')))} figures to {FIGDIR}")


if __name__ == "__main__":
    main()
