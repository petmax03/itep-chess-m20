import sys,json,io
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R;sys.path.insert(0,str(R/'vendor'))
import chess,chess.engine,chess.pgn
p=H/'test-results/v16.1/uci-modes.pgn';e=chess.engine.SimpleEngine.popen_uci([sys.executable,str(R/'uci.py')],timeout=30)
try:
 e.configure({'PGNFile':str(p),'ForcedPlay':'checks','ChecksPerSide':3})
 b=chess.Board();b.push_uci('e2e4');a=e.play(b,chess.engine.Limit(depth=3))
 g=chess.pgn.read_game(io.StringIO(p.read_text()));assert not g.errors and g.end().move==a.move
 assert g.headers['M20ForcedPlay']=='checks' and g.headers['M20ChecksPerSide']=='3'
 b.push(a.move);b.push_uci('d2d4');e.configure({'ForcedPlay':'wide'})
 a=e.play(b,chess.engine.Limit(depth=3));g=chess.pgn.read_game(io.StringIO(p.read_text()))
 assert not g.errors and g.end().move==a.move
 assert g.headers['M20ForcedPlay']=='wide'
 assert g.headers['M20ForcedPlayHistory']=='checks:3, wide'
 assert '[%m20_forced checks:3]' in p.read_text() and '[%m20_forced wide]' in p.read_text()
 assert int(g.headers['M20TotalCommands'])>0
 print('UCI_PGN_HEADERS_MIXED_MODES_CLOCKS_OK')
finally:e.quit()
(H/'test-results/v16.1/uci-pgn-check.json').write_text(json.dumps({'headers':dict(g.headers),'plies':g.end().ply(),'success':True},ensure_ascii=False,indent=2))
