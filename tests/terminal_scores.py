#!/usr/bin/env python3
"""Check the actual native-node score at both terminal entry points."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess

cases=[
 ('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1',False),
 ('8/8/8/8/8/6k1/5q2/7K w - - 0 1',False),
 ('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1',True),
 ('8/8/8/8/8/6k1/6q1/7K w - - 0 1',True)]
rows=[]
for fen,mate in cases:
 b=chess.Board(fen);side=not b.turn
 assert b.is_checkmate() if mate else b.is_stalemate()
 row=dict(fen=fen,mate=mate,entries=[])
 for entry,end in [(0o4042,0o4064),(0o4111,0o4136)]:
  m=Machine();m.reset();m.encode(b);m.mem[0o1700]=int(side)<<12;m.ra.value=int(side)
  m.run(entry,end,4)
  score=m.mem[0o7460+int(side)]
  assert score==(0 if mate else m.mem[0o1102]),(fen,entry,score)
  # Complement (5), the parent's operation at 4100.
  parent=m.mem[0o1074]-score
  assert parent==(m.mem[0o1074] if mate else m.mem[0o1102])
  row['entries'].append(dict(entry=f'{entry:04o}',score=f'{score:015o}',parent_score=f'{parent:015o}'))
 row['score']=row['entries'][0]['score'];rows.append(row)
out=ROOT/'test-results/v19.1';out.mkdir(parents=True,exist_ok=True)
(out/'terminal-scores.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS: both colors, mate/stalemate, both native node entry points')
