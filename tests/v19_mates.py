#!/usr/bin/env python3
"""Original 20 mates, both Nb6# depth checks, and v19.1 promotion regression."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess
rows=[]
for i,case in enumerate(json.loads((ROOT/'tests/mate-in-one.json').read_text()),1):
 for depth in ((1,2,3,4,5) if i<=2 else (1,2,3)):
  result=Machine().think(chess.Board(case['fen']),depth)
  assert result.get('move') in case['mates'],(i,depth,result)
  rows.append(dict(case=i,fen=case['fen'],depth=depth,answer=result))
baseline=json.loads((ROOT/'test-results/v19/mates.json').read_text())
old={(x['case'],x['depth']):x['answer'] for x in baseline}
changes={key:sum(x['answer'][key]!=old[x['case'],x['depth']][key] for x in rows) for key in ('move','nodes','steps','word')}
assert all(changes[key]==0 for key in ('move','nodes','word')),changes
mate_summary={'positions':20,'searches':len(rows),'changed':changes,'command_deltas':[
 dict(case=x['case'],depth=x['depth'],delta=x['answer']['steps']-old[x['case'],x['depth']]['steps'])
 for x in rows if x['answer']['steps']!=old[x['case'],x['depth']]['steps']]}
print(f'PASS: {len(rows)} original searches; all selected mating moves unchanged.',flush=True)
regressions=[]
initial=chess.Board('1r2k3/P7/8/8/8/8/8/3QK3 w - - 0 1')
promotion=initial.copy()
promotion.push_san('Qd7+');promotion.push_san('Kf8')
finish=promotion.copy();finish.push_san('axb8=Q#');assert finish.is_checkmate()
for color in (chess.WHITE,chess.BLACK):
 for fixture,parent in [('initial',initial),('promotion_mate',promotion)]:
  board=parent.copy() if color else parent.mirror()
  for depth in (1,2,3):
   result=Machine().think(board,depth)
   move=chess.Move.from_uci(result['move']);assert move in board.legal_moves
   if fixture=='promotion_mate':
    child=board.copy();child.push(move)
    assert move.promotion==chess.QUEEN and child.is_checkmate(),result
   elif depth>=2:
    assert move.uci()==('a7b8q' if color else 'a2b1q'),result
   regressions.append(dict(fixture=fixture,color='white' if color else 'black',fen=board.fen(),depth=depth,answer=result))
   print('PASS promotion',fixture,'white' if color else 'black',depth,result['san'],flush=True)
dest=ROOT/'test-results/v19.1/mates.json';dest.parent.mkdir(parents=True,exist_ok=True)
dest.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
(dest.parent/'mates-summary.json').write_text(json.dumps(mate_summary,indent=2)+'\n')
(dest.parent/'promotion-search.json').write_text(json.dumps(regressions,ensure_ascii=False,indent=2))
print(f'PASS: {len(rows)} original searches plus {len(regressions)} promotion searches.')
