#!/usr/bin/env python3
"""All 73 nonblank depth-3 historical decisions and available user game 6."""
import concurrent.futures as cf,ctypes as C,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess,CommandLimitError
from engine.build import build
import chess.pgn
OUT=ROOT/'test-results/v18/comparison'
def run(job):
 dest=OUT/(job['id']+'.json')
 if dest.exists():return json.loads(dest.read_text())
 b=chess.Board(job['initial_fen'])
 for u in job['moves']:b.push_uci(u)
 row={**job,'fen':b.fen()}
 for flag,key in [(False,'before'),(True,'after')]:
  m=Machine(terminal_rules=flag)
  try:row[key]=m.think(b,3,budget=job['budget'])
  except CommandLimitError as e:row[key]={'error':'limit',**e.measurement()}
  except Exception as e:row[key]={'error':str(e)}
  row[key]['terminal_stats']=list((C.c_uint64*3).in_dll(m.lib,'itef_terminal_stats'))
 row['changed']=row['before'].get('move')!=row['after'].get('move')
 dest.write_text(json.dumps(row,ensure_ascii=False,indent=2));return row
if __name__=='__main__':
 OUT.mkdir(parents=True,exist_ok=True);build();jobs=[]
 counts=json.loads((ROOT/'tests/historical-position-counts.json').read_text())
 with (ROOT/'tests/historical-games.pgn').open() as f:games=[chess.pgn.read_game(f) for _ in range(2)]
 for c in counts:
  if c['game'] not in (1,2) or c['count'] is None or c['nominal_depth']!=3:continue
  g=games[c['game']-1];b=g.board();ply=2*(c['move_number']-1)+(c['color']=='black')
  if ply>=len(list(g.mainline_moves())):continue
  assert list(g.mainline_moves())[ply].uci()==c['historical_uci']
  for move in list(g.mainline_moves())[:ply]:b.push(move)
  jobs.append(dict(id=f"history-g{c['game']}-p{ply+1}",group='history',game=c['game'],ply=ply+1,initial_fen=b.root().fen(),moves=[m.uci() for m in b.move_stack],reference=c['historical_uci'],historical_nodes=c['count'],budget=3_000_000_000))
 assert len(jobs)==73,len(jobs)
 with (ROOT/'examples/itef-game-6.pgn').open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
 b=g.board()
 color=chess.WHITE if 'ИТЭФ' in g.headers['White'] else chess.BLACK
 for move in g.mainline_moves():
  if b.turn==color:
   jobs.append(dict(id=f'game6-p{b.ply()+1}',group='game6',ply=b.ply()+1,initial_fen=b.root().fen(),moves=[m.uci() for m in b.move_stack],reference=move.uci(),budget=20_000_000_000))
  b.push(move)
 if not b.is_game_over() and b.turn==color:
  jobs.append(dict(id=f'game6-p{b.ply()+1}',group='game6',ply=b.ply()+1,initial_fen=b.root().fen(),moves=[m.uci() for m in b.move_stack],reference=None,budget=20_000_000_000))
 with cf.ProcessPoolExecutor(max_workers=4) as pool:
  for row in pool.map(run,jobs):print(row['id'],row['before'].get('san'),row['after'].get('san'),'CHANGED' if row['changed'] else '=',flush=True)
