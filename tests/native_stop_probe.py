#!/usr/bin/env python3
"""Optional reproduction of the old quiet-08 fault; uses a temporary build.

It observes the first overwrite of code at 3402 without changing the release.
The v19 promotion repair is deliberately disabled for this archival test.
"""
import ctypes as C,json,shutil,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='m20-watch-') as td:
 scratch=Path(td)
 for name in ('engine','m20','research','vendor'):
  shutil.copytree(ROOT/name,scratch/name,ignore=shutil.ignore_patterns('__pycache__','*.so','*.dylib'))
 p=scratch/'engine/bridge.c';source=p.read_text()
 source=source.replace('#include "terminal.h"','#include "terminal.h"\nuint64_t watch_write[12];')
 old='r=cpu_one_inst(); if(r) return -r;'
 assert old in source
 source=source.replace(old,'''uint64_t previous=M[03402],oldrk=RK,oldra=RA,oldpc=RVK,oldrank=M[01700];
        r=cpu_one_inst();
        if(M[03402]!=previous) {
            watch_write[0]=i;watch_write[1]=oldrk;watch_write[2]=oldra;
            watch_write[3]=oldpc;watch_write[4]=oldrank;
            watch_write[5]=previous;watch_write[6]=M[03402];
            watch_write[7]=M[07461];watch_write[8]=M[01704];
            return -9998;
        }
        if(r) return -r;''')
 p.write_text(source);sys.path.insert(0,str(scratch))
 from engine.machine import Machine,chess
 pos=next(x for x in json.loads((ROOT/'benchmarks/positions.json').read_text()) if x['id']=='quiet-08')
 b=chess.Board(pos['initial_fen'])
 for u in pos['moves']:b.push_uci(u)
 m=Machine(promotion_repair=False)
 try:result=m.think(b,5,budget=20_000_000_000)
 except Exception as error:
  result=dict(error=str(error),position=pos,watch_write=list((C.c_uint64*12).in_dll(m.lib,'watch_write')),
   watch_fields='command_index rk ra next_pc rank old_3402 new_3402 score_7461 pointer_1704 reserved reserved reserved'.split())
 dest=ROOT/'test-results/v19/native-stop-legacy-reproduced.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(dest);print(result.get('error','No overwrite detected'))
