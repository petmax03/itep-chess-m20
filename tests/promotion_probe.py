#!/usr/bin/env python3
"""Find the first native occupancy/figure-table mismatch, without a host FEN reset.

Run with --without-repair to reproduce the fault, or without arguments to
verify quiet-08 depth 5 to completion. The temporary observer is not shipped
as part of the playable bridge and does not affect M-20 command counts.
"""
import argparse, ctypes as C, json, shutil, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--without-repair',action='store_true');a=p.parse_args()
with tempfile.TemporaryDirectory(prefix='m20-promotion-') as td:
 scratch=Path(td)
 for name in ('engine','m20','research','vendor'):
  shutil.copytree(ROOT/name,scratch/name,ignore=shutil.ignore_patterns('__pycache__','*.so','*.dylib'))
 p=scratch/'engine/bridge.c';source=p.read_text()
 assert '#include "terminal.h"' in source and 'if(!RK_inject_flag) terminal_before(RVK);' in source
 source=source.replace('#include "terminal.h"','#include "terminal.h"\n'+(ROOT/'tests/promotion_watch.h').read_text())
 source=source.replace('if(!RK_inject_flag) terminal_before(RVK);','if(audit_board(RVK))return -9090;\n        if(!RK_inject_flag) terminal_before(RVK);')
 source=source.replace('forced_reset();','forced_reset();audit_count=0;audit_fail=0;')
 p.write_text(source);sys.path.insert(0,str(scratch))
 from engine.machine import Machine,chess
 from engine.promotion_slots import PATCH
 pos=next(x for x in json.loads((ROOT/'benchmarks/positions.json').read_text()) if x['id']=='quiet-08')
 board=chess.Board(pos['initial_fen'])
 for u in pos['moves']:board.push_uci(u)
 m=Machine(promotion_repair=not a.without_repair)
 try:answer=m.think(board,5,budget=20_000_000_000)
 except Exception as e:answer={'error':str(e)}
 count=C.c_uint64.in_dll(m.lib,'audit_count').value
 bad=C.c_uint64.in_dll(m.lib,'audit_fail').value
 ring=((C.c_uint64*96)*256).in_dll(m.lib,'audit_rows')
 rows=[list(ring[i%256]) for i in range(max(0,count-256),count)]
 result=dict(repair=not a.without_repair,position=pos,answer=answer,count=count,bad=bad,
             rows=rows,mem=list(m.mem),pc=m.pc.value,ra=m.ra.value)
 out=ROOT/'test-results/v19';out.mkdir(parents=True,exist_ok=True)
 dest=out/('promotion-before.json' if a.without_repair else 'promotion-after.json')
 dest.write_text(json.dumps(result,ensure_ascii=False,indent=2))
 if a.without_repair:
  assert bad==1 and m.pc.value==0o2220,answer
 else:
  assert not bad and answer.get('move')=='d6c7',answer
  assert all(m.mem[k]==v for k,v in PATCH.items()), 'Overlay memory modified'
  assert m.mem[0o3402]==m.base[0o3402], 'Move generator code modified'
 print(dict(answer=answer,checkpoints=count,mismatch=bad,output=str(dest)))
