import sys,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];H=R;sys.path.insert(0,str(R/'vendor'))
import chess,chess.engine,chess.pgn
engine=chess.engine.SimpleEngine.popen_uci([sys.executable,str(R/'uci.py')],timeout=30)
rows=[]
try:
 assert engine.options['ForcedPlay'].default=='listing'
 assert engine.options['ChecksPerSide'].default==2
 b=chess.Board();b.push_uci('e2e4')
 for mode,n in [('listing',2),('narrow',2),('checks',3),('wide',2)]:
  engine.configure({'ForcedPlay':mode,'ChecksPerSide':n})
  ans=engine.play(b,chess.engine.Limit(depth=3),info=chess.engine.INFO_ALL)
  assert ans.move in b.legal_moves
  tag=f'checks:{n}' if mode=='checks' else mode
  assert 'forced_play '+tag in ans.info['string'],ans.info
  rows.append({'mode':mode,'N':n,'move':ans.move.uci(),'nodes':ans.info['nodes'],'info':ans.info['string']})
 with (R/'examples/itef-machack.pgn').open() as f:b=chess.pgn.read_game(f).end().board()
 b.pop();b.pop()
 engine.configure({'ForcedPlay':'wide','CommandLimitMillions':50})
 ans=engine.play(b,chess.engine.Limit(depth=3),info=chess.engine.INFO_ALL)
 assert ans.info['depth']==2 and 'forced_play wide' in ans.info['string'],ans.info
 rows.append({'fallback_depth':ans.info['depth'],'mode':'wide','move':ans.move.uci(),'info':ans.info['string']})
finally:engine.quit()
(H/'test-results/v16.1/uci-check.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
