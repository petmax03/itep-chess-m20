import sys,json,io,time,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R;sys.path.insert(0,str(R))
from play import Game,chess
from engine.forced_play import ForcedPlay
from engine.machine import CommandLimitError
import chess.pgn
out={}
def wait(g):
 deadline=time.monotonic()+30
 while g.busy and time.monotonic()<deadline:time.sleep(.02)
 assert not g.busy and not g.error,(g.busy,g.error)
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'game.json';g=Game(p)
 assert g.machine.forced_play.variant=='listing'
 g.action({'action':'settings','forced_variant':'checks','checks_per_side':3})
 assert Game(p).machine.forced_play==ForcedPlay('checks',3)
 before=g.machine.forced_play
 for x in [-1,100,1.5,'2',None,True]:
  try:g.action({'action':'settings','forced_variant':'wide','checks_per_side':x})
  except ValueError:pass
  else:raise AssertionError(x)
  assert g.machine.forced_play==before
 g.action({'action':'move','move':'e4'});wait(g)
 assert g.records[-1]['forced_play']['checks_per_side']==3
 g.action({'action':'settings','forced_variant':'narrow'})
 move=next(iter(g.board.legal_moves));g.action({'action':'move','move':move.uci()});wait(g)
 assert g.move_forced==[None,'checks:3',None,'narrow']
 text=g.pgn();pg=chess.pgn.read_game(io.StringIO(text));assert not pg.errors
 assert pg.headers['M20ForcedPlay']=='narrow'
 assert pg.headers['M20ForcedPlayHistory']=='checks:3, narrow'
 assert '[%m20_forced checks:3]' in text and '[%m20_forced narrow]' in text
 q=Path(td)/'saved.pgn';q.write_text(text)
 loaded=Game();loaded.load_pgn(q,'white');assert loaded.machine.forced_play.variant=='narrow'
 assert loaded.move_forced[1]=='checks:3' and loaded.move_forced[3]=='narrow'
 g.action({'action':'undo'});assert len(g.records)==len(g.move_forced)==len(g.board.move_stack)==2
 legacy=json.loads(p.read_text());legacy.pop('forced_play');legacy.pop('move_forced');p.write_text(json.dumps(legacy))
 assert Game(p).machine.forced_play==ForcedPlay()
 loaded.load_pgn(R/'examples/itef-machack.pgn','black');assert loaded.machine.forced_play==ForcedPlay()
 # Pause, change rule, reduce: both attempted modes survive in the record/PGN.
 paused=Game();paused.human=chess.BLACK;paused.depth=3
 paused.start_engine(budget=1000);wait(paused);assert paused.pending['limit']['forced_play']['variant']=='listing'
 paused.action({'action':'settings','forced_variant':'checks','checks_per_side':1})
 paused.action({'action':'reduce'});wait(paused)
 assert paused.last['depth']==2 and paused.last['forced_play']['checks_per_side']==1
 assert paused.last['attempts'][0]['forced_play']['variant']=='listing'
 assert paused.last['attempts'][1]['forced_play']['variant']=='checks'
 assert 'listing → checks:1' in paused.pgn()
 (H/'test-results/v16.1/mixed-modes.pgn').write_text(text)
 (H/'test-results/v16.1/limit-mode-change.pgn').write_text(paused.pgn())
 out={'persistence':True,'invalid_values_rejected':True,'mixed_pgn_roundtrip':True,'undo':True,'legacy_defaults_to_listing':True,'limit_reduce_preserves_modes':True,'measured_moves':2}
(H/'test-results/v16.1/app-check.json').write_text(json.dumps(out,indent=2));print(out)
