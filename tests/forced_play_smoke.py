#!/usr/bin/env python3
"""Golden v16/v15 results, admission extremes, and PGN settings round-trip."""
import io,json,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess
from engine.forced_play import ForcedPlay
from play import Game
import chess.pgn
KEYS=('move','nodes','steps','word','lambda_final_1706','search_mode')
evidence=json.loads((ROOT/'test-results/v16.1/engine-check.json').read_text())
a=chess.Board();a.push_uci('e2e4')
with (ROOT/'examples/itef-machack.pgn').open(encoding='utf-8') as f:
 g=chess.pgn.read_game(f)
assert not g.errors
b=g.end().board();assert b.ply()==74;b.pop();b.pop()
for board,ref in zip((a,b),evidence['baseline']):
 ans=Machine().think(board)
 assert all(ans[k]==ref['old'][k] for k in KEYS),(ans,ref)
with (ROOT/'tests/historical-games.pgn').open(encoding='utf-8') as f:
 chess.pgn.read_game(f);g=chess.pgn.read_game(f)
b=g.board()
for move in list(g.mainline_moves())[:19]:b.push(move)
for ref in evidence['golden_v15']:
 ans=Machine(forced_variant=ref['variant'],checks_per_side=ref['N']).think(b)
 assert all(ans[k]==ref['reference'][k] for k in KEYS),(ans,ref)
for v,n in [('narrow',0),('wide',99)]:
 x=Machine(forced_variant=v).think(a);y=Machine(forced_variant='checks',checks_per_side=n).think(a)
 assert all(x[k]==y[k] for k in KEYS)
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'game.json';game=Game(p)
 game.action({'action':'settings','forced_variant':'checks','checks_per_side':3})
 assert Game(p).machine.forced_play==ForcedPlay('checks',3)
 game.action({'action':'move','move':'e4'})
 deadline=time.monotonic()+30
 while game.busy and time.monotonic()<deadline:time.sleep(.02)
 assert not game.busy and not game.error
 text=game.pgn();pg=chess.pgn.read_game(io.StringIO(text))
 assert pg.headers['M20ForcedPlay']=='checks' and pg.headers['M20ChecksPerSide']=='3'
 assert '[%m20_forced checks:3]' in text
 q=Path(td)/'game.pgn';q.write_text(text,encoding='utf-8')
 loaded=Game();loaded.load_pgn(q,'white');assert loaded.machine.forced_play==ForcedPlay('checks',3)
print('PASS: v16 listing; v15 narrow/N=1/N=2; N=0/99; saved settings; PGN round-trip')
