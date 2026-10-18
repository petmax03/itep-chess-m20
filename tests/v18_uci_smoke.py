#!/usr/bin/env python3
import io,json,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'vendor'))
import chess,chess.engine,chess.pgn
out=R/'test-results/v18';p=out/'uci-depths.pgn';e=chess.engine.SimpleEngine.popen_uci([sys.executable,str(R/'uci.py')],timeout=60)
rows=[]
try:
 assert e.options['Depth'].default==3 and e.options['Depth'].min==3 and e.options['Depth'].max==5
 assert e.options['CommandLimitMillions'].default==0
 e.configure({'PGNFile':str(p)})
 b=chess.Board('1nk2b1r/rp4pp/p3Np2/2p4b/2N2B2/3P4/PPP2PPP/R4K1R w - - 4 20')
 for d in (3,4,5):
  a=e.play(b,chess.engine.Limit(depth=d),info=chess.engine.INFO_ALL);assert b.san(a.move)=='Nb6#' and a.info['depth']==d
  g=chess.pgn.read_game(io.StringIO(p.read_text()));assert g.headers['SearchDepth']==str(d)
  assert f'[%m20_depth {d}]' in p.read_text();rows.append(dict(depth=d,move=a.move.uci(),nodes=a.info['nodes']))
 b=chess.Board();b.push_uci('e2e4');e.configure({'Depth':5,'CommandLimitMillions':1})
 a=e.play(b,chess.engine.Limit(depth=5),info=chess.engine.INFO_ALL)
 assert a.move in b.legal_moves and a.info['depth']==4
 assert '[%m20_fallback 4]' in p.read_text() and '[SearchDepth "5"]' in p.read_text()
 rows.append(dict(requested=5,fallback=4,move=a.move.uci(),info=a.info))
 # Other forced options still remain usable after depth configuration.
 for mode in ('narrow','checks','wide'):
  e.configure({'ForcedPlay':mode,'ChecksPerSide':1,'CommandLimitMillions':0})
  a=e.play(b,chess.engine.Limit(depth=3));assert a.move in b.legal_moves
finally:e.quit()
(out/'uci-check.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str))
print('PASS: UCI depths 3/4/5, mate, auto budget, real 5→4 fallback, PGN, forced modes')
