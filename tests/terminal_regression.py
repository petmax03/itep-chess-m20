#!/usr/bin/env python3
"""Independent terminal oracle + seeded mate corpus + native search checks."""
import ctypes as C,json,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess
import chess.pgn
OUT=ROOT/'test-results/v18';OUT.mkdir(exist_ok=True)
rng=random.Random(1804)
def mates(b):
 found=[]
 for m in list(b.legal_moves):
  b.push(m);yes=b.is_checkmate();b.pop()
  if yes:found.append(m.uci())
 return found
corpus=[]
def add(b,source):
 mm=mates(b)
 if mm and b.fen() not in {x['fen'] for x in corpus}:
  corpus.append(dict(fen=b.fen(),source=source,mates=mm))
for fen in ['1nk2b1r/rp4pp/p3Np2/2p4b/2N2B2/3P4/PPP2PPP/R4K1R w - - 4 20','1nk5/rp6/p3N3/8/2N5/8/8/4K3 w - - 0 1']:
 add(chess.Board(fen),'user-v18')
for p in sorted((ROOT/'examples').glob('*.pgn')):
 with p.open(encoding='utf-8-sig') as f:g=chess.pgn.read_game(f)
 b=g.board()
 for move in g.mainline_moves():
  if len(corpus)<8:add(b,p.name+f': before ply {b.ply()+1}')
  b.push(move)
for pieces in ['Q','R','RR','RB','RN','QP','Q','R','QB','QN','RP','Q']*3:
 if len(corpus)>=20:break
 for attempt in range(50000):
  b=chess.Board(None);squares=rng.sample(range(64),len(pieces)+2)
  for sq,piece in zip(squares,'Kk'+pieces):b.set_piece_at(sq,chess.Piece.from_symbol(piece))
  if not b.is_valid():continue
  if len(corpus)%2:b=b.mirror()
  n=len(corpus);add(b,'generated seed 1804: '+pieces)
  if len(corpus)>n:break
assert len(corpus)==20
(ROOT/'tests/mate-in-one.json').write_text(json.dumps(corpus,ensure_ascii=False,indent=2))
m=Machine();m.lib.itef_terminal_kind.argtypes=[C.c_uint];m.lib.itef_terminal_kind.restype=C.c_int
oracle=[]
def check(b,source):
 if not b.is_valid():return
 try:m.reset();m.encode(b)
 except Exception:return # historical format does not represent arbitrary underpromotion slots
 got=m.lib.itef_terminal_kind(not b.turn)
 expected=1 if b.is_checkmate() else 2 if b.is_stalemate() else 0
 assert got==expected,(source,b.fen(),got,expected)
 oracle.append(dict(fen=b.fen(),source=source,kind=got))
for x in corpus:
 b=chess.Board(x['fen']);check(b,'mate parent')
 for move in b.legal_moves:
  c=b.copy();c.push(move);check(c,'mate corpus child')
# Terminal and near-terminal random boards; both colors. Include pawn masks.
for _ in range(12000):
 b=chess.Board(None);pieces='Kk'+rng.choice(['Q','R','QR','PPp','RR','BPp','NN','Qp','RPp'])
 for sq,piece in zip(rng.sample(range(64),len(pieces)),pieces):b.set_piece_at(sq,chess.Piece.from_symbol(piece))
 b.turn=bool(rng.randrange(2));check(b,'random seed 1804')
for fen in ['7k/5Q2/6K1/8/8/8/8/8 b - - 0 1','8/8/8/8/8/6k1/5q2/7K w - - 0 1','r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1','8/8/8/3pP3/8/8/8/K6k w - d6 0 1','8/8/8/r4pPK/8/8/8/7k w - f6 0 1']:
 check(chess.Board(fen),'explicit stalemate/castling/ep')
# Thousands of reachable boards, including all legal child positions with ep.
for game in range(12):
 b=chess.Board()
 for ply in range(150):
  check(b,'random legal walk')
  if b.ep_square:
   for move in b.legal_moves:
    c=b.copy();c.push(move);check(c,'ep child')
  if b.is_game_over():break
  b.push(rng.choice(list(b.legal_moves)))
results=[]
for i,x in enumerate(corpus):
 for depth in (1,2,3):
  b=chess.Board(x['fen']);row=dict(case=i+1,source=x['source'],fen=b.fen(),depth=depth)
  for enabled,key in [(False,'before'),(True,'after')]:
   try:
    a=Machine(terminal_rules=enabled).think(b,depth);row[key]=a
    a['mate_in_one']=a.get('move') in x['mates']
   except Exception as e:row[key]={'error':str(e),'mate_in_one':False}
  results.append(row);print(i+1,depth,row['before'].get('san'),row['after'].get('san'),row['after']['mate_in_one'],flush=True)
summary=dict(corpus=20,searches=len(results)*2,after_mates=sum(r['after']['mate_in_one'] for r in results),before_mates=sum(r['before']['mate_in_one'] for r in results),oracle_positions=len(oracle),oracle_mates=sum(r['kind']==1 for r in oracle),oracle_stalemates=sum(r['kind']==2 for r in oracle))
(OUT/'terminal-search.json').write_text(json.dumps(dict(summary=summary,rows=results),ensure_ascii=False,indent=2))
(OUT/'terminal-oracle.json').write_text(json.dumps(oracle,ensure_ascii=False,indent=2))
print(summary,flush=True)
assert summary['after_mates']==60
