#!/usr/bin/env python3
"""Fixed corpus, raw depth trials (no extensions/fallback), resumable on Mac/Linux."""
import argparse,concurrent.futures as cf,hashlib,json,platform,statistics,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,CommandLimitError,chess
from engine.depth_policy import DEPTH_BUDGETS
import chess.pgn

def corpus():
 pools={'quiet':[],'check':[]}
 for name in ['itef-game-3.pgn','itef-game-4.pgn','itef-game-6.pgn','itef-machack.pgn']:
  with (ROOT/'examples'/name).open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
  assert g and not g.errors
  b=g.board();group={'quiet':[],'check':[]}
  for move in g.mainline_moves():
   if 10<=b.fullmove_number<=30 and len(b.piece_map())>=12:
    category='check' if b.is_check() else 'quiet' if not any(b.gives_check(m) for m in b.legal_moves) and sum(b.is_capture(m) for m in b.legal_moves)<=2 else None
    if category:
     group[category].append(dict(game=name,ply=b.ply()+1,turn='white' if b.turn else 'black',fullmove=b.fullmove_number,
       fen=b.fen(),moves=[m.uci() for m in b.move_stack],initial_fen=b.root().fen(),category=category,legal_moves=b.legal_moves.count(),pieces=len(b.piece_map())))
   b.push(move)
  for category in pools:
   if group[category]:pools[category].append(group[category])
 selected=[]
 for category in pools:
  # Round-robin games, evenly spaced within each game's eligible positions;
  # selected before any run. No timing or outcome informs the sample.
  groups=pools[category];allocation=[0]*len(groups)
  for i in range(10):
   eligible=[j for j,g in enumerate(groups) if allocation[j]<len(g)]
   j=min(eligible,key=lambda j:(allocation[j],j));allocation[j]+=1
  for group,n in zip(groups,allocation):
   indices=[round(i*(len(group)-1)/(n-1)) for i in range(n)] if n>1 else [len(group)//2]
   selected += [group[i] for i in indices]
 for i,p in enumerate(selected,1):p['id']=f'{p["category"]}-{i:02d}'
 assert len(selected)==20 and len({p['fen'] for p in selected})==20
 return selected

def fingerprint():
 paths=['engine/machine.py','engine/bridge.c','engine/forced_play.h','engine/forced_board.h','engine/terminal.h','engine/search_profiles.py','engine/native_rank_capacity.py',
        'engine/promotion_slots.py','m20/simh/m20_cpu.c','m20/kaissa/kaissa.m20','research/low-constants.m20','research/standard-cells-values.m20']
 return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}

def run_one(task):
 pos,depth,out=task;dest=Path(out)/f'{pos["id"]}-d{depth}.json'
 if dest.exists():return json.loads(dest.read_text())
 b=chess.Board(pos['initial_fen'])
 for u in pos['moves']:b.push_uci(u)
 assert b.fen()==pos['fen']
 m=Machine();start=time.perf_counter();cpu=time.process_time()
 row=dict(position=pos['id'],category=pos['category'],depth=depth,budget=DEPTH_BUDGETS[depth])
 try:
  a=m.think(b,depth,budget=row['budget']);row.update(status='answered',move=a['move'],nodes=a['nodes'],steps=a['steps'],engine_seconds=a['seconds'])
 except CommandLimitError as e:row.update(status='limit',move=None,nodes=e.nodes,steps=e.steps,engine_seconds=e.seconds)
 except Exception as e:row.update(status='error',error=str(e),move=None,nodes=None,steps=None)
 row.update(seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
 tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps(row,indent=2));tmp.replace(dest)
 return row

def summarize(out):
 out=Path(out);rows=[json.loads(p.read_text()) for p in out.glob('*-d[345].json')];meta=json.loads((out/'machine.json').read_text());stats=[]
 for category in ('quiet','check','all'):
  for depth in (3,4,5):
   rr=[r for r in rows if r['depth']==depth and (category=='all' or r['category']==category)]
   good=[r for r in rr if r['status']!='error'];done=[r for r in rr if r['status']=='answered']
   item=dict(category=category,depth=depth,n=len(rr),answered=len(done),limits=sum(r['status']=='limit' for r in rr),errors=sum(r['status']=='error' for r in rr))
   item['limit_fraction']=item['limits']/len(rr) if rr else None
   for key in ('nodes','steps','seconds','cpu_seconds'):
    values=[r[key] for r in good];completed=[r[key] for r in done]
    item[key]={'median':statistics.median(values) if values else None,'max':max(values) if values else None,
      'completed_median':statistics.median(completed) if completed else None,'completed_max':max(completed) if completed else None}
   stats.append(item)
 result=dict(machine=meta,rows=stats,completed_trials=len(rows),expected_trials=60)
 (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 lines=['M20 '+(ROOT/'VERSION').read_text().strip()+' — raw depth benchmark',f"Machine: {meta['platform']}; workers={meta['workers']}",
 'Raw search to its base limit; no fallback. Med/max include censored work at limits, not full-tree estimates.',
 'Completed-only figures and per-position results are in summary.json.',
 '| Group | Depth | Completed | Limits | Errors | Positions med / max | Commands med / max | Host seconds med / max |',
 '|---|---:|---:|---:|---:|---:|---:|---:|']
 for r in stats:
  def pair(k):return f"{r[k]['median']:.2f} / {r[k]['max']:.2f}" if r[k]['median'] is not None else '—'
  lines.append(f"| {r['category']} | {r['depth']} | {r['answered']}/{r['n']} | {r['limits']}/{r['n']} | {r['errors']}/{r['n']} | {pair('nodes')} | {pair('steps')} | {pair('seconds')} |")
 (out/'REPORT.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines),flush=True)

def main():
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=1);p.add_argument('--output',type=Path,default=ROOT/'benchmark-results'/('mac' if platform.system()=='Darwin' else 'linux'));p.add_argument('--make-corpus',action='store_true');p.add_argument('--summary',action='store_true');a=p.parse_args()
 if a.make_corpus:
  (ROOT/'benchmarks/positions.json').write_text(json.dumps(corpus(),ensure_ascii=False,indent=2));return
 if a.summary:summarize(a.output);return
 if not 1<=a.workers<=8:p.error('workers: 1..8')
 positions=json.loads((ROOT/'benchmarks/positions.json').read_text());a.output.mkdir(parents=True,exist_ok=True)
 meta={'platform':platform.platform(),'system':platform.system(),'machine':platform.machine(),'processor':platform.processor(),'python':sys.version,'workers':a.workers,'source':fingerprint(),
       'corpus_sha256':hashlib.sha256((ROOT/'benchmarks/positions.json').read_bytes()).hexdigest(),'date_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 if platform.system()=='Darwin':
  meta['mac_model']=subprocess.check_output(['sysctl','-n','hw.model'],text=True).strip();meta['cpu']=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
 mp=a.output/'machine.json'
 if mp.exists():
  old=json.loads(mp.read_text())
  if any(old[k]!=meta[k] for k in ('source','corpus_sha256','platform','workers')):p.error('Existing results have a different source/host/worker count; choose another --output.')
 else:mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2))
 Machine() # compile before child workers
 tasks=[(pos,d,str(a.output)) for d in (3,4,5) for pos in positions]
 if a.workers==1:
  iterator=map(run_one,tasks)
  for r in iterator:print(r['position'],r['depth'],r['status'],r.get('steps'),round(r['seconds'],2),flush=True)
 else:
  with cf.ProcessPoolExecutor(max_workers=a.workers) as pool:
   for r in pool.map(run_one,tasks):print(r['position'],r['depth'],r['status'],r.get('steps'),round(r['seconds'],2),flush=True)
 summarize(a.output)
if __name__=='__main__':main()
