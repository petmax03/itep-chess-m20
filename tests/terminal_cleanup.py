#!/usr/bin/env python3
"""A terminal child must not expose a previous branch's candidate to its parent.

Seed the stale rook entry found in the failing trace; require an empty child
list, unchanged neighbor slots, and the correct mate/stalemate score. Exercise
both native entry points and both pointer-array layouts, including rank 16.
"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess,CommandLimitError
from engine.search_profiles import PROFILES
STALE=0o046617500046204
cases=[('mate','7k/6Q1/6K1/8/8/8/8/8 b - - 0 1'),
       ('stalemate','Q7/8/1k6/8/2Q5/8/8/4K3 b - - 0 1')]
rows=[]
for profile in PROFILES:
 for kind,fen in cases:
  for mirror in (False,True):
   board=chess.Board(fen)
   if mirror:board=board.mirror()
   side=not board.turn
   assert board.is_checkmate() if kind=='mate' else board.is_stalemate()
   for rank in ((int(side),12+int(side),16) if not side else (1,13)):
    for entry,end in [(0o4042,0o4064),(0o4111,0o4136)]:
     m=Machine(profile=profile);m.reset();m.encode(board)
     base=m.mem[0o4675]&0o7777
     m.mem[0o1700]=rank<<12;m.ra.value=rank
     m.mem[base+rank]=STALE
     m.mem[base+rank-1]=0o1234567;m.mem[base+rank+1]=0o7654321
     m.mem[0o7460+rank]=0o1234
     m.run(entry,end,4)
     assert m.mem[base+rank]==0,(profile,kind,rank,entry)
     assert m.mem[base+rank-1]==0o1234567 and m.mem[base+rank+1]==0o7654321
     assert m.mem[0o7460+rank]==(0 if kind=='mate' else m.mem[0o1102])
     rows.append(dict(profile=profile,kind=kind,rank=rank,entry=f'{entry:04o}',pointer=f'{base+rank:04o}',score=f'{m.mem[0o7460+rank]:015o}'))
 # Live nodes must still execute the normal entry instruction without overlay writes.
 for entry in (0o4042,0o4111):
  m=Machine(profile=profile);m.reset();m.encode(chess.Board())
  base=m.mem[0o4675]&0o7777;m.mem[0o1700]=0;m.ra.value=0
  m.mem[base]=STALE;m.mem[0o7460]=0o1234
  try:m.run(entry,0o6000,1)
  except CommandLimitError:pass
  assert m.mem[base]==STALE and m.mem[0o7460]==0o1234
out=ROOT/'test-results/v19.1';out.mkdir(parents=True,exist_ok=True)
(out/'terminal-cleanup.json').write_text(json.dumps(rows,indent=2))
print(f'PASS: {len(rows)} terminal exits; both colors and entry points; all profiles; live nodes unchanged.')
