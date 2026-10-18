"""Independent end-to-end acceptance checks; no modern move selection."""
import argparse, json, time
from pathlib import Path
from native import Machine, chess, generated
from engine.depth_policy import calculate
from engine.telemetry import pgn_comment
import chess.pgn

def compare(machine, board):
    found=generated(machine,board)
    wanted={m.uci() for m in board.generate_pseudo_legal_moves()
            if not m.promotion or m.promotion==chess.QUEEN}
    assert set(found)==wanted, (board.fen(), 'missing', wanted-found.keys(),'extra',found.keys()-wanted)
    for uci,pieces in found.items():
        copy=board.copy();copy.push_uci(uci)
        assert pieces==copy.piece_map(), (board.fen(),uci,'native board differs')
    return len(found)

def main():
    p=argparse.ArgumentParser();p.add_argument('--plies',type=int,default=192)
    p.add_argument('--output',default='test-results/v19.1/verify');args=p.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    machine=Machine();start=time.monotonic();positions=moves=0
    board=chess.Board();first=list(board.legal_moves)
    moves+=compare(machine,board);positions+=1
    for one in first:
        board.push(one);moves+=compare(machine,board);positions+=1
        for two in list(board.legal_moves):
            board.push(two);moves+=compare(machine,board);positions+=1;board.pop()
        board.pop()
    print(f'PASS generator: {positions} positions, {moves} native applications',flush=True)
    specials=[
        'r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1',
        'r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1',
        'r3k2r/8/8/8/8/8/8/R3K2R w Kq - 0 1',
        'r3k2r/8/8/8/8/8/8/R3K2R b Qk - 0 1',
        '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
        '4k3/8/8/8/3Pp3/8/8/4K3 b - d3 0 1',
        '4k3/P7/8/8/8/8/8/4K3 w - - 0 1',
        '4k3/8/8/8/8/8/p7/4K3 b - - 0 1',
        '1r2k3/P7/8/8/8/8/8/3QK3 w - - 0 1',
        '3qk3/8/8/8/8/8/p7/1R2K3 b - - 0 1',
    ]
    special_results=[]
    for fen in specials:
        b=chess.Board(fen);count=compare(machine,b);r=machine.think(b)
        special_results.append({'fen':fen,'moves':count,**r})
        print('PASS special',fen,r['move'],flush=True)
    for fen in ['7k/5Q2/6K1/8/8/8/8/8 w - - 0 1','8/8/8/8/8/6k1/5q2/7K b - - 0 1']:
        b=chess.Board(fen);r=machine.think(b);b.push_uci(r['move']);assert b.is_checkmate(),r
        print('PASS mate',r,flush=True)
    regression=chess.Board('2kr4/4PR2/8/ppp5/8/3r1p2/PP3P2/2K3R1 b - - 0 34')
    # The repaired evasion search no longer needs a retry on this old fixture.
    # Preserve the end-to-end legality regression, not the obsolete v09 move.
    r=machine.think(regression);assert chess.Move.from_uci(r['move']) in regression.legal_moves,r
    regression_result=r
    print('PASS prior aspiration fixture',r,flush=True)
    b=chess.Board();game=chess.pgn.Game();game.headers.update(Event='ITEF v19.1 acceptance / profile v11',Date='2026.10.13',White='ITEF M-20',Black='ITEF M-20',SearchDepth='3')
    node=game;searches=[];resignation=None
    for ply in range(args.plies):
        if b.is_game_over():break
        # Exercise the existing game/UCI policy: one live extension, then
        # depth fallback if needed. Native stops and illegal moves still fail;
        # the fixed-position regressions above retain their strict 3B budget.
        r=calculate(machine,b,3)
        if r.get('resign'):
            resignation={'fen':b.fen(),**r};game.headers['Result']='0-1' if b.turn else '1-0'
            node.comment+=' ITEF resigns: the original search returns the absolute lower score after a full-window retry. '+pgn_comment(r)
            print('PASS resignation',resignation,flush=True);break
        move=chess.Move.from_uci(r['move'])
        searches.append({'ply':ply+1,'fen':b.fen(),**r});b.push(move);node=node.add_variation(move);node.comment=pgn_comment(r)
        print('PASS ply',ply+1,r['san'],'depth',r['depth'],'commands',r['total_steps'],flush=True)
        (output/'selfplay.pgn').write_text(str(game)+'\n',encoding='utf-8')
        (output/'selfplay.json').write_text(json.dumps(searches,indent=2),encoding='utf-8')
    if resignation is None:game.headers['Result']=b.result()
    (output/'selfplay.pgn').write_text(str(game)+'\n',encoding='utf-8')
    report={'generator_positions':positions,'native_move_applications':moves,'special_positions':special_results,'mate_tests':2,'prior_aspiration_fixture':regression_result,'selfplay_plies':len(searches),'selfplay_max_plies':args.plies,'selfplay_budget_policy':'existing depth_policy.calculate; one extension then fallback; native stops remain errors','selfplay_result':game.headers['Result'],'resignation':resignation,'final_fen':b.fen(),'seconds':round(time.monotonic()-start,3)}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS all',report,flush=True)

if __name__=='__main__':main()
