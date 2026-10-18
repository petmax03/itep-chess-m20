#!/usr/bin/env python3
"""Fixed-depth UCI transport. Only the preserved native M-20 chooses moves."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

from engine.machine import Machine, CommandLimitError, chess
from engine.build import build
from engine.search_profiles import DEFAULT_PROFILE, PROFILES
from engine.forced_play import ForcedPlay, VARIANTS, MAX_CHECKS
from engine.uci_pgn import UCIPGN
from engine.telemetry import minutes
from engine.depth_policy import DEPTH_BUDGETS, calculate as search_with_policy

ROOT=Path(__file__).resolve().parent


def calculate(job):
    board=chess.Board(job['fen'])
    for move in job['moves']:board.push_uci(move)
    if board.is_game_over():return {'status':'terminal','move':None}
    forced=ForcedPlay.from_metadata(job.get('forced_play'))
    machine=Machine(profile=job['profile'],forced_variant=forced.variant,checks_per_side=forced.checks_per_side)
    depth=job['depth'];start=time.monotonic()
    try:
        result=search_with_policy(machine,board,depth,job.get('budget'))
        result['status']='answered';result['wall_ms']=round((time.monotonic()-start)*1000)
        return result
    except CommandLimitError as exc:
        return {'status':'limit','error':'No completed move within the command budget at depth 2',
                'move':None,'attempts':exc.attempts,'last_limit':exc.measurement()}



class UCI:
    def __init__(self, profile=DEFAULT_PROFILE, depth=3, budget=None,
                 forced_variant='listing', checks_per_side=2):
        self.board=chess.Board();self.profile=profile;self.depth=depth;self.budget=budget
        self.forced_play=ForcedPlay(forced_variant,checks_per_side)
        self.pgn=UCIPGN()
        self.lock=threading.RLock();self.output_lock=threading.Lock()
        self.process=None;self.generation=0

    def emit(self, line):
        with self.output_lock:
            print(line,flush=True)

    def cancel(self, report=False):
        with self.lock:
            process=self.process
            if process is None:return
            self.generation+=1;self.process=None
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            if report:
                self.emit('info string M20 search cancelled; no completed answer retained')
                self.emit('bestmove 0000')

    def set_position(self, tokens):
        if not tokens:raise ValueError('position requires startpos or fen')
        if tokens[0]=='startpos':board=chess.Board();rest=tokens[1:]
        elif tokens[0]=='fen':
            if len(tokens)<7:raise ValueError('fen requires six fields')
            board=chess.Board(' '.join(tokens[1:7]));rest=tokens[7:]
        else:raise ValueError('unknown position format')
        if not board.is_valid():raise ValueError('invalid chess position')
        if rest:
            if rest[0]!='moves':raise ValueError('expected moves')
            for move in rest[1:]:board.push_uci(move)
        self.cancel();self.board=board
        self.write_pgn()

    def write_pgn(self):
        try:self.pgn.write(self.board,self.forced_play)
        except OSError as exc:self.emit('info string M20 PGN write failed: '+str(exc))

    def set_option(self, tokens):
        if not tokens or tokens[0].lower()!='name':return
        lower=[x.lower() for x in tokens]
        at=lower.index('value') if 'value' in lower else len(tokens)
        name=' '.join(lower[1:at]);value=' '.join(tokens[at+1:])
        with self.lock:
            if self.process is not None:raise ValueError('setoption while searching')
            if name=='profile':
                if value not in PROFILES:raise ValueError('unknown profile')
                self.profile=value
            elif name=='depth':
                depth=int(value)
                if depth not in (3,4,5):raise ValueError('depth must be 3, 4 or 5')
                self.depth=depth
            elif name=='commandlimitmillions':
                value=int(value)
                if not 0<=value<=20000:raise ValueError('CommandLimitMillions must be 0 (automatic) .. 20000')
                self.budget=value*1_000_000 if value else None
            elif name=='forcedplay':
                self.forced_play=ForcedPlay(value.lower(),self.forced_play.checks_per_side)
            elif name=='checksperside':
                self.forced_play=ForcedPlay(self.forced_play.variant,int(value))
            elif name=='pgnfile':
                self.pgn.path=Path(value).expanduser() if value and value!='<empty>' else None

    def go(self, tokens):
        depth=self.depth
        if 'depth' in tokens:depth=int(tokens[tokens.index('depth')+1])
        if depth not in (3,4,5):raise ValueError('depth must be 3, 4 or 5')
        unsupported=set(tokens)&{'infinite','ponder','searchmoves','nodes','mate','movetime'}
        if unsupported:raise ValueError('fixed-depth wrapper does not implement '+','.join(sorted(unsupported)))
        if set(tokens)&{'wtime','btime','winc','binc','movestogo'}:
            self.emit('info string M20 uses fixed depth and command budget; wall-clock limits are not implemented')
        self.cancel()
        job={'fen':self.board.root().fen(),'moves':[m.uci() for m in self.board.move_stack],
             'profile':self.profile,'depth':depth,'budget':self.budget or DEPTH_BUDGETS[depth],'forced_play':self.forced_play.metadata()}
        self.emit('info string M20 forced_play '+self.forced_play.tag())
        process=subprocess.Popen([sys.executable,str(ROOT/'uci.py'),'--worker'],stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        with self.lock:
            self.generation+=1;generation=self.generation;self.process=process
        def watch():
            try:
                output,error=process.communicate(json.dumps(job))
                result=json.loads(output)
            except Exception as exc:
                result={'status':'error','error':str(exc),'move':None}
            with self.lock:
                if generation!=self.generation:return
                self.process=None
                if result['status']=='answered':
                    move=result.get('move') or '0000'
                    try:self.pgn.answer(self.board,result,ForcedPlay.from_metadata(job['forced_play']))
                    except OSError as exc:self.emit('info string M20 PGN write failed: '+str(exc))
                    if result['depth_reduced']:
                        self.emit(f"info string M20 command limit reached at depth {depth}; fallback depth {result['depth']}; path "+' '.join(map(str,result['fallback_depths'])))
                    for extension in result.get('extensions',[]):
                        self.emit(f"info string M20 continued depth {extension['depth']} extra_commands {extension['extra']}")
                    self.emit(f"info depth {result['depth']} nodes {result['nodes']} time {result['wall_ms']}"+
                              (f' pv {move}' if move!='0000' else ''))
                    self.emit(f"info string M20 commands {result['steps']} minutes {minutes(result['steps']):.6f} "
                              f"total_commands {result['total_steps']} total_minutes {minutes(result['total_steps']):.6f} profile {job['profile']} "
                              f"forced_play {ForcedPlay.from_metadata(job['forced_play']).tag()}")
                    if result.get('resign'):self.emit('info string M20 native resignation')
                    self.emit('bestmove '+move)
                else:
                    if result.get('error'):self.emit('info string M20 '+str(result['error']).replace('\n',' '))
                    self.emit('bestmove 0000')
        threading.Thread(target=watch,daemon=True).start()

    def run(self):
        try:
            for line in sys.stdin:
                words=line.split()
                if not words:continue
                command=words[0]
                try:
                    if command=='uci':
                        self.emit('id name ITEF M-20 v19.1')
                        self.emit('id author ITEF original authors; reconstruction Maxim / Astra')
                        self.emit(f"option name Profile type combo default {self.profile}"+''.join(' var '+p for p in PROFILES))
                        self.emit(f'option name Depth type spin default {self.depth} min 3 max 5')
                        self.emit(f'option name CommandLimitMillions type spin default {(self.budget or 0)//1_000_000} min 0 max 20000')
                        self.emit(f'option name ForcedPlay type combo default {self.forced_play.variant}'+''.join(' var '+v for v in VARIANTS))
                        self.emit(f'option name ChecksPerSide type spin default {self.forced_play.checks_per_side} min 0 max {MAX_CHECKS}')
                        self.emit('option name PGNFile type string default <empty>')
                        self.emit('uciok')
                    elif command=='isready':build();self.emit('readyok')
                    elif command=='position':self.set_position(words[1:])
                    elif command=='setoption':self.set_option(words[1:])
                    elif command=='ucinewgame':self.cancel();self.board=chess.Board();self.pgn.clear()
                    elif command=='go':self.go(words[1:])
                    elif command=='stop':self.cancel(report=True)
                    elif command=='quit':break
                except (ValueError,IndexError,RuntimeError) as exc:
                    self.emit('info string M20 '+str(exc).replace('\n',' '))
                    if command=='go':self.emit('bestmove 0000')
        finally:self.cancel()


def main():
    parser=argparse.ArgumentParser(description='Fixed-depth UCI wrapper for the ITEF M-20')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--profile',choices=tuple(PROFILES),default=DEFAULT_PROFILE)
    parser.add_argument('--depth',type=int,choices=(3,4,5),default=3)
    parser.add_argument('--budget',type=int,help='override automatic depth budget; default: 3/10/20 billion')
    parser.add_argument('--forced-play',choices=tuple(VARIANTS),default='listing')
    parser.add_argument('--checks-per-side',type=int,choices=range(MAX_CHECKS+1),default=2,metavar='N')
    args=parser.parse_args()
    if args.worker:
        try:result=calculate(json.load(sys.stdin))
        except Exception as exc:result={'status':'error','error':str(exc),'move':None}
        print(json.dumps(result,ensure_ascii=False),flush=True)
    else:
        if args.budget is not None and not 1_000_000<=args.budget<=20_000_000_000:parser.error('budget must be 1 million .. 20 billion')
        UCI(args.profile,args.depth,args.budget,args.forced_play,args.checks_per_side).run()

if __name__=='__main__':main()
