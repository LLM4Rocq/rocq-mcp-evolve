"""Read-only content-provenance census: every non-blank line of the graded proof body must
appear, whitespace-normalized, in the attempt's own record: transcript tool_use inputs, assistant
text, tool_result contents, and our server.jsonl. Reports per-arm counts and every row that fails."""
import json, os, glob, re, collections, sys
from pathlib import Path
sys.path.insert(0,'harness'); import gate
LOGS=Path('logs'); norm=lambda s: re.sub(r'\s+','',s)
C=collections.Counter(); fails=[]
for p in sorted(glob.glob('logs/runs/FINAL_*/results.jsonl')):
    run=os.path.basename(os.path.dirname(p))
    arm='sibling' if 'rocqmcp' in run else ('control' if 'baseline' in run else 'session')
    for l in open(p):
        r=json.loads(l)
        if not r['solved']: continue
        ad=LOGS/r['attempt_dir']; w=ad/'work'
        subs=sorted((w/'submissions').glob('*.v'),reverse=True) if (w/'submissions').exists() else []
        art=subs[0] if subs else w/'candidate.v'
        cand=art.read_text(); pre=(ad/'task_prefix.v').read_text(); sp=gate.split_at_prefix(cand,pre); body=cand[sp:] if sp is not None else cand
        lines=[norm(x) for x in body.splitlines() if len(norm(x))>=8]
        parts=[]
        tr=ad/'transcript.jsonl'
        if tr.exists():
            for line in open(tr):
                try: e=json.loads(line)
                except Exception: continue
                m=e.get('message') or {}; cont=m.get('content')
                if isinstance(cont,list):
                    for c in cont:
                        t=c.get('type')
                        if t=='tool_use': parts.append(json.dumps(c.get('input'),ensure_ascii=False))
                        elif t=='text': parts.append(c.get('text') or '')
                        elif t=='tool_result':
                            cc=c.get('content'); parts.append(cc if isinstance(cc,str) else json.dumps(cc,ensure_ascii=False))
                elif isinstance(cont,str): parts.append(cont)
        if (ad/'server.jsonl').exists(): parts.append((ad/'server.jsonl').read_text())
        raw=''.join(parts); blob=norm(raw); blob2=norm(raw.replace('\\n','\n').replace('\\"','"').replace('\\\\','\\'))
        missing=[x for x in lines if x not in blob and x not in blob2]
        C[(arm,'full' if not missing else 'partial')]+=1
        if missing: fails.append((run,r['problem_id'],r['rep'],round(1-len(missing)/len(lines),2),[m[:60] for m in missing[:2]]))
for k,v in sorted(C.items()): print('  ',v,k)
print('solved rows with lines not found in own record:', len(fails)); [print('   ',x) for x in fails[:30]]
