#!/usr/bin/env python3
"""Replay reference positions; the reference move is never a search argument."""
import argparse,csv,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.machine import Machine,chess
import chess.pgn

def save(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pgn',type=Path,default=ROOT/'tests/historical-games.pgn')
    p.add_argument('--out',type=Path,default=ROOT/'test-results/history')
    p.add_argument('--depth',type=int,choices=range(1,6),default=3)
    p.add_argument('--games',default='1,2')
    p.add_argument('--budget',type=int,default=3_000_000_000)
    p.add_argument('--resume',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    games=set(map(int,a.games.split(',')))
    files=[*ROOT.glob('engine/*.py'),*ROOT.glob('engine/*.c'),*ROOT.glob('m20/**/*') ,*ROOT.glob('research/*.m20')]
    digests={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest()
             for x in sorted(files) if x.is_file() and x.suffix in ('.py','.c','.h','.m20')}
    manifest={'version':(ROOT/'VERSION').read_text().strip(),'depth':a.depth,'games':sorted(games),
              'budget_per_run':a.budget,'source_sha256':digests,
              'pgn_sha256':hashlib.sha256(a.pgn.read_bytes()).hexdigest(),
              'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    manifest_path=a.out/'manifest.json';rows_path=a.out/'comparison.json'
    if a.resume and rows_path.exists():
        if not manifest_path.exists() or json.loads(manifest_path.read_text())!=manifest:
            p.error('Исходники, PGN или настройки изменились: используйте новую папку --out.')
        rows=json.loads(rows_path.read_text())
    else:
        rows=[];save(manifest_path,manifest)
    done={(r['game'],r['ply']) for r in rows};machine=Machine()
    with a.pgn.open(encoding='utf-8') as source:
        gid=0
        while (game:=chess.pgn.read_game(source)) is not None:
            gid+=1
            if gid not in games:continue
            if game.errors:raise RuntimeError(game.errors)
            board=game.board();color=chess.WHITE if 'ITEP' in game.headers['White'].upper() else chess.BLACK
            for ply,reference in enumerate(game.mainline_moves(),1):
                if board.turn==color and (gid,ply) not in done:
                    row={'game':gid,'ply':ply,'move_number':board.fullmove_number,'fen':board.fen(),
                         'historical_depth':game.headers.get('PlyDepth','?'),'tested_depth':a.depth,
                         'historical_uci':reference.uci(),'historical_san':board.san(reference)}
                    try:
                        answer=machine.think(board,a.depth,budget=a.budget)
                        row.update(answer);row['match']=answer['move']==reference.uci()
                    except Exception as exc:
                        row.update(error=f'{type(exc).__name__}: {exc}',match=None)
                    rows.append(row);save(rows_path,rows)
                    print(json.dumps({k:row.get(k) for k in ('game','ply','historical_san','san','match','error')},ensure_ascii=False),flush=True)
                board.push(reference)
    rows.sort(key=lambda r:(r['game'],r['ply']));save(rows_path,rows)
    summary=[]
    for gid in sorted(games):
        group=[r for r in rows if r['game']==gid]
        answered=sum('error' not in r for r in group);matches=sum(r['match'] is True for r in group)
        summary.append({'game':gid,'tested':len(group),'answered':answered,'matches':matches,
                        'different':sum(r['match'] is False for r in group),'unanswered':len(group)-answered,
                        'percent_of_all_positions':round(100*matches/len(group),2) if group else None})
    save(a.out/'summary.json',summary)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (a.out/'comparison.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
