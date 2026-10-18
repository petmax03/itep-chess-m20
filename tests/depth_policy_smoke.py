#!/usr/bin/env python3
import io,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess,CommandLimitError
from engine.depth_policy import calculate,DEPTH_BUDGETS
from engine.telemetry import pgn_comment
from play import Game
import chess.pgn
OUT=ROOT/'test-results/v19.1';OUT.mkdir(parents=True,exist_ok=True)
def wait(g):
 deadline=time.monotonic()+60
 while g.busy and time.monotonic()<deadline:time.sleep(.01)
 assert not g.busy and not g.error,(g.busy,g.error)
b=chess.Board();b.push_uci('e2e4')
a=Machine().think(b,3);paused=[]
c=Machine().think(b,3,budget=1_000_000,on_limit=lambda e:(paused.append(e.measurement()) or 20_000_000))
keys=('move','nodes','steps','word','search_mode')
assert all(a[k]==c[k] for k in keys)
# Real live continuation, larger than half of the measured answer.
g=Game();g.board=b.copy();g.records=[None];g.comments=[''];g.move_forced=[None]
g.start_engine(budget=6_000_000);wait(g);assert g.waiting and g.pending['limit']['steps']==6_000_000
assert g.totals()['steps']==6_000_000
g.action({'action':'continue'});wait(g)
assert g.last['steps']==a['steps'] and g.last['total_steps']==a['steps']
assert g.last['extensions']==[dict(depth=3,extra=6_000_000)]
assert '[%m20_depth 3]' in g.pgn()
# A genuinely insufficient cap is extended once, then falls back one level.
g=Game();g.board=b.copy();g.records=[None];g.comments=[''];g.move_forced=[None];g.depth=5
g.start_engine(budget=500_000);wait(g);g.action({'action':'continue'});wait(g)
assert g.last['depth']==4,g.last
assert g.last['fallback_depths']==[4]
assert g.last['attempts'][0]['steps']==1_000_000
assert '[%m20_fallback 4]' in g.pgn() and '[SearchDepth "5"]' in g.pgn()
(OUT/'depth-fallback.pgn').write_text(g.pgn())
# Persisted checkpoint: stop old thread, restore and account replay separately.
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'game.json';x=Game(p);x.board=b.copy();x.records=[None];x.comments=[''];x.move_forced=[None]
 x.start_engine(budget=6_000_000);wait(x);x.cancel_pause()
 y=Game(p);assert not y.waiting and y.pending['limit']
 y.action({'action':'continue'});wait(y)
 assert y.last['total_steps']==a['steps']+6_000_000 and y.last['resume_replayed']
 assert '[%m20_replay 1]' in y.pgn()
 y.action({'action':'settings','depth':5});z=Game(p);assert (z.depth,z.budget)==(5,20_000_000_000)
 q=Path(td)/'g.pgn';q.write_text(y.pgn());z.load_pgn(q);assert z.depth==5
# Explicit reduce drops a single level; board replacement releases paused CPU.
g=Game();g.human=chess.BLACK;g.depth=5;g.start_engine(budget=1000);wait(g)
g.action({'action':'reduce'});wait(g);assert g.last['depth']==4
x=Game();x.human=chess.BLACK;x.start_engine(budget=1000);wait(x);thread=x.worker_thread
x.action({'action':'new','side':'white','depth':3});assert not thread.is_alive() and not x.busy
# Entire automatic 5 -> 4 -> 3 -> 2 ladder with bounded synthetic work.
class Bounded:
 def __init__(self):self.calls=[]
 def think(self,board,depth,budget,on_limit):
  self.calls.append((depth,budget))
  if depth==2:return dict(move='a2a3',san='a3',depth=2,steps=17,nodes=3,seconds=0)
  e=CommandLimitError(budget,budget,9,0);e.depth=depth
  extra=on_limit(e)
  if extra:e.steps+=extra;e.budget+=extra
  raise e
f=Bounded();r=calculate(f,chess.Board(),5)
assert [d for d,_ in f.calls]==[5,4,3,2]
assert r['fallback_depths']==[4,3,2]
assert r['total_steps']==40_000_000_000+10_000_000_000+3_000_000_000+17
assert all(f'[%m20_fallback {d}]' in pgn_comment(r) for d in [4,3,2])
(OUT/'depth-policy.json').write_text(json.dumps(dict(default=a,resumed=c,checkpoints=paused,ladder=r),ensure_ascii=False,indent=2))
print('PASS: exact live continuation; one extension; single-level fallback; complete ladder; PGN; restart accounting; settings; cancellation')
