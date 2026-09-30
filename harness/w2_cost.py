#!/usr/bin/env python3
"""Estimate wave-2 policy spend from transcripts (killed attempts report
cost=0 in results.jsonl, so sum per-message usage incl. thinking)."""
import json, glob, sys
RATE_IN, RATE_OUT, RATE_CR, RATE_CW = 3e-6, 15e-6, 0.3e-6, 3.75e-6
def cost(tp):
    tot = 0.0
    for l in open(tp):
        try: e = json.loads(l)
        except: continue
        if e.get('type') == 'result' and e.get('total_cost_usd') is not None:
            return e['total_cost_usd'], 'result'
        if e.get('type') == 'assistant':
            u = e.get('message', {}).get('usage', {})
            tot += (u.get('input_tokens',0)*RATE_IN + u.get('output_tokens',0)*RATE_OUT
                    + u.get('cache_read_input_tokens',0)*RATE_CR
                    + u.get('cache_creation_input_tokens',0)*RATE_CW)
    # add estimated thinking tokens (billed as output) not captured above
    th = 0
    for l in open(tp):
        try: e = json.loads(l)
        except: continue
        if e.get('subtype') == 'thinking_tokens':
            th = max(th, e.get('estimated_tokens', 0))
    return tot + th*RATE_OUT, 'estimated'
grand = 0.0
rows = []
for tp in sorted(glob.glob('logs/autoform/*/attempts/*/transcript.jsonl')):
    run = tp.split('autoform/')[1].split('/')[0]
    if not run.startswith('w2_'): continue
    a = tp.split('attempts/')[1].split('/transcript')[0]
    c, src = cost(tp); grand += c
    rows.append((run, a, c, src))
for run, a, c, src in rows:
    print(f'{run:18s} {a:22s} ${c:6.3f}  {src}')
print(f'--- wave-2 estimated cumulative policy spend: ${grand:.2f} (cap $60) ---')
