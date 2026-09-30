#!/usr/bin/env python3
"""Read-only lineage check over the FINAL_* runs: every results.jsonl row against the CLI
transcript it was recorded from (init model, result-event cost/turns) and against our server
log (tool-call count); every solved row must have its graded artifact; transcript mtime must
fall inside the attempt window. Run from the repo root: python3 harness/lineage_check.py
Expected (2026-09-02): init_model_match == rows; solved_with_artifact == solved rows; every
mismatch confined to files rewritten after the attempt deadline (A83/A93/A110e classes)."""
import json, os, glob, collections
from pathlib import Path
LOGS=Path('logs'); C=collections.Counter(); bad=collections.defaultdict(list)
def last_json_line(p, want):
    # scan from the end for the last event of a given type without loading whole file
    with open(p,'rb') as f:
        f.seek(0,2); size=f.tell(); buf=b''; pos=size
        while pos>0:
            step=min(65536,pos); pos-=step; f.seek(pos); buf=f.read(step)+buf
            for line in reversed(buf.split(b'\n')):
                if not line.strip(): continue
                try: e=json.loads(line)
                except Exception: continue
                if e.get('type')==want: return e
            if len(buf)>4_000_000: break
    return None
for p in sorted(glob.glob('logs/runs/FINAL_*/results.jsonl')):
    run=os.path.basename(os.path.dirname(p))
    for l in open(p):
        r=json.loads(l); C['rows']+=1
        ad=LOGS/r['attempt_dir']; tr=ad/'transcript.jsonl'
        if not tr.exists():
            parked=list(ad.glob('transcript*.jsonl'))+list(ad.glob('*.parked*'))
            C['no_transcript']+=1; bad['no_transcript'].append((run,r['problem_id'],r['rep'],len(parked))); continue
        with open(tr) as f: first=f.readline()
        try: init=json.loads(first)
        except Exception: init={}
        model_ok = (init.get('type')=='system' and init.get('subtype')=='init' and init.get('model')==r['model'])
        C['init_model_match' if model_ok else 'init_model_MISMATCH']+=1
        if not model_ok: bad['init_model'].append((run,r['problem_id'],r['rep'],init.get('model'),r['model']))
        res=last_json_line(tr,'result')
        if res is None:
            C['no_result_event']+=1
            if not r.get('attempt_timed_out'): bad['no_result_not_timed_out'].append((run,r['problem_id'],r['rep']))
        else:
            cost_ok = abs((res.get('total_cost_usd') or 0)-(r.get('total_cost_usd') or 0))<1e-9
            C['cost_match' if cost_ok else 'cost_MISMATCH']+=1
            if not cost_ok: bad['cost'].append((run,r['problem_id'],r['rep'],res.get('total_cost_usd'),r.get('total_cost_usd')))
            turns_ok = res.get('num_turns')==r.get('num_turns')
            C['turns_match' if turns_ok else 'turns_MISMATCH']+=1
        sl=ad/'server.jsonl'
        if sl.exists():
            n=sum(1 for x in open(sl) if '"tool_call"' in x)
            ok = n==r.get('tool_calls')
            C['server_toolcalls_match' if ok else 'server_toolcalls_MISMATCH']+=1
            if not ok: bad['server_toolcalls'].append((run,r['problem_id'],r['rep'],n,r.get('tool_calls')))
        else:
            C['no_server_log']+=1
        if r['solved']:
            w=ad/'work'; has=(w/'candidate.v').exists() or ((w/'submissions').exists() and any((w/'submissions').glob('*.v')))
            C['solved_with_artifact' if has else 'solved_NO_ARTIFACT']+=1
            if not has: bad['solved_no_artifact'].append((run,r['problem_id'],r['rep']))
        # timestamp bracket: transcript mtime should be within [ts, ts+wall+60]
        m=os.path.getmtime(tr); 
        if not (r['ts']-5 <= m <= r['ts']+r['wall_s']+60): C['transcript_mtime_outside_window']+=1; bad['mtime'].append((run,r['problem_id'],r['rep'],round(m-r['ts'])))
print(json.dumps(C, indent=1))
for k,v in bad.items(): print(k, len(v), v[:6])
