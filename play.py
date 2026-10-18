#!/usr/bin/env python3
"""Local chess board and command-line operator for the original M-20 search."""
import argparse
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shutil
import threading
import time
import webbrowser

from engine.machine import Machine, MachineError, CommandLimitError, chess
from engine.search_profiles import DEFAULT_PROFILE, PROFILES
from engine.forced_play import ForcedPlay, VARIANTS, MAX_CHECKS, comment_tag
from engine.telemetry import (DEFAULT_BUDGET, CONTINUE_BUDGET, BUDGET_CHOICES,
    COMMANDS_PER_MINUTE, minutes, format_time, completed_record, pgn_comment)
from engine.depth_policy import DEPTH_BUDGETS, calculate, SearchCancelled
import chess.pgn

ROOT=Path(__file__).resolve().parent

class Game:
    def __init__(self, save_path=None, machine_options=None, budget=None, depth=None):
        self.machine=Machine(**(machine_options or {}))
        self.lock=threading.RLock()
        self.board=chess.Board()
        self.human=chess.WHITE
        self.depth=3
        self.budget=DEFAULT_BUDGET
        self.busy=False
        self.error=''
        self.last=None
        self.resigned=None
        self.records=[]
        self.comments=[]
        self.move_forced=[]
        self.pending=None
        self.worker_thread=None
        self.resume_event=threading.Event()
        self.resume_choice=None
        self.waiting=False
        self.save_path=save_path
        if save_path and save_path.exists():
            try:
                state=json.loads(save_path.read_text(encoding='utf-8'))
                restored=chess.Board(state.get('initial_fen',chess.STARTING_FEN))
                for move in state['moves']:restored.push_uci(move)
                if not restored.is_valid():raise ValueError('Invalid saved board')
                self.board=restored
                self.human=state['human']=='white'
                self.resigned=state.get('resigned')
                self.depth=int(state.get('depth',3))
                if self.depth not in (3,4,5):self.depth=3
                self.budget=DEPTH_BUDGETS[self.depth]
                n=len(self.board.move_stack)
                self.records=(state.get('records',[])+[None]*n)[:n]
                self.comments=(state.get('comments',[])+['']*n)[:n]
                self.move_forced=(state.get('move_forced',[])+['listing']*n)[:n]
                self.machine.forced_play=ForcedPlay.from_metadata(state.get('forced_play'))
                self.last=state.get('last')
                p=state.get('pending')
                if p and p.get('fen')==self.board.fen():
                    self.pending=p
                    p['live']=False
                    p.setdefault('base_budget',DEPTH_BUDGETS[p.get('requested_depth',3)])
                    if state.get('version') not in ('17','18') and p.get('limit'):
                        # v16 counted the paused checkpoint as a separate attempt.
                        if p['attempts'] and p['attempts'][-1]==p['limit']:p['attempts'].pop()
                        p['checkpoint_counted']=False
            except (OSError,ValueError,KeyError,TypeError) as e:
                self.error='Не удалось прочитать сохранённую партию: '+str(e)
        options=machine_options or {}
        if 'forced_variant' in options or 'checks_per_side' in options:
            current=self.machine.forced_play
            self.machine.forced_play=ForcedPlay(options.get('forced_variant',current.variant),
                                               options.get('checks_per_side',current.checks_per_side))
        if budget is not None:
            if budget not in BUDGET_CHOICES:raise ValueError('Игровой лимит: 3, 10 или 20 млрд команд.')
            self.budget=budget
        if depth is not None:
            if depth not in (3,4,5):raise ValueError('Игровая глубина: 3, 4 или 5.')
            self.depth=depth
            if budget is None:self.budget=DEPTH_BUDGETS[depth]

    def load_pgn(self, path, human=None):
        with Path(path).open(encoding='utf-8-sig') as f:game=chess.pgn.read_game(f)
        if game is None or game.errors:raise ValueError('Не удалось прочитать легальную партию PGN.')
        board=game.end().board()
        forced=ForcedPlay.from_headers(game.headers)
        if not board.is_valid():raise ValueError('Некорректная позиция PGN.')
        if self.save_path and self.save_path.exists():
            backup=self.save_path.with_name('game-before-import-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.json')
            shutil.copy2(self.save_path,backup)
        self.board=board
        self.human=(human=='white') if human else ('ИТЭФ' not in game.headers.get('White',''))
        self.records=[None]*len(board.move_stack)
        self.comments=[n.comment for n in game.mainline()]
        self.machine.forced_play=forced
        self.depth=int(game.headers.get('SearchDepth',3))
        if self.depth not in (3,4,5):self.depth=3
        self.budget=DEPTH_BUDGETS[self.depth]
        self.move_forced=[comment_tag(n.comment,forced.tag()) for n in game.mainline()]
        self.pending=None;self.last=None;self.resigned=None;self.error=''
        self.save()

    def save(self):
        if self.save_path:
            data={'version':'18','initial_fen':self.board.root().fen(),'moves':[m.uci() for m in self.board.move_stack],
                  'human':'white' if self.human else 'black','depth':self.depth,'budget':self.budget,
                  'resigned':self.resigned,'records':self.records,'comments':self.comments,
                  'pending':self.pending,'last':self.last,'search_profile':self.machine.search_settings.metadata()}
            data.update(forced_play=self.machine.forced_play.metadata(),move_forced=self.move_forced)
            temp=self.save_path.with_suffix('.tmp')
            temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(self.save_path)

    def cancel_pause(self):
        """Release the waiting frame before replacing its board or CPU settings."""
        with self.lock:
            if not self.waiting:return
            thread=self.worker_thread
            self.resume_choice='cancel';self.resume_event.set()
        if thread:thread.join(timeout=5)
        if thread and thread.is_alive():raise RuntimeError('Не удалось остановить ожидающий расчёт.')

    def start_engine(self, depth=None, budget=None, retry=False, extend=True):
        with self.lock:
            if self.busy or self.waiting or self.board.turn==self.human or self.board.is_game_over() or self.resigned is not None:return
            if self.pending and self.pending.get('limit') and not retry:return
            board=self.board.copy()
            depth=self.depth if depth is None else depth
            budget=self.budget if budget is None else budget
            if not self.pending or self.pending['fen']!=board.fen():
                self.pending={'fen':board.fen(),'requested_depth':self.depth,'attempts':[],'limit':None}
            pending=self.pending
            # A checkpoint loaded from disk cannot retain the live CPU frame.
            # Its replay is an additional, explicitly accounted calculation.
            if pending.get('limit') and not pending.get('checkpoint_counted'):
                pending['attempts'].append(pending['limit'])
            pending.update(limit=None,base_budget=budget,current_depth=depth,live=False,checkpoint_counted=False)
            self.busy=True;self.error=''
        def progress(current,attempts):
            with self.lock:
                pending.update(current_depth=current,attempts=list(attempts),limit=None,
                               live=False,checkpoint_counted=False)
                self.busy=True;self.save()
        def pause(exc):
            with self.lock:
                self.resume_event.clear();self.resume_choice=None
                pending.update(limit=exc.measurement(),live=True,checkpoint_counted=False)
                self.waiting=True;self.busy=False;self.save()
            self.resume_event.wait()
            with self.lock:
                choice=self.resume_choice
                self.waiting=False
                if choice=='cancel':raise SearchCancelled()
                pending.update(limit=None,live=False)
                self.busy=True
            return choice
        def worker():
            try:
                record=calculate(self.machine,board,depth,budget,pause=pause,progress=progress,
                                 attempts=pending['attempts'],requested_depth=pending['requested_depth'],extend=extend)
                if pending.get('replayed'):record['resume_replayed']=True
                with self.lock:
                    if record.get('resign'):self.resigned=board.turn
                    else:
                        self.board.push_uci(record['move']);self.records.append(record);self.comments.append('')
                        self.move_forced.append(ForcedPlay.from_metadata(record.get('forced_play')).tag())
                    self.last=record;self.pending=None;self.save()
            except SearchCancelled:pass
            except CommandLimitError as exc:
                with self.lock:
                    pending.update(attempts=exc.attempts,limit=exc.measurement(),exhausted=True,
                                   live=False,checkpoint_counted=True)
                    self.error='Лимит достигнут и на глубине 2. Позиция сохранена.';self.save()
            except Exception as exc:
                with self.lock:self.error=str(exc);self.save()
            finally:
                with self.lock:self.busy=False;self.waiting=False
        self.worker_thread=threading.Thread(target=worker,daemon=True)
        self.worker_thread.start()

    def totals(self):
        records=[r for r in self.records if r]
        if self.resigned is not None and self.last:records.append(self.last)
        completed=sum(r['steps'] for r in records)
        total=sum(r['total_steps'] for r in records)
        if self.pending:
            total+=sum(a['steps'] for a in self.pending['attempts'])
            if self.pending.get('limit') and not self.pending.get('checkpoint_counted'):
                total+=self.pending['limit']['steps']
        return {'steps':total,'minutes':minutes(total),'text':format_time(total),
                'completed_steps':completed,'retry_steps':total-completed,
                'recorded_moves':sum(r is not None for r in self.records)}

    def status(self):
        with self.lock:
            b=self.board;limit=self.pending.get('limit') if self.pending else None
            if self.error:message=self.error
            elif self.busy:message=f"ИТЭФ думает… Глубина {self.pending.get('current_depth',self.depth) if self.pending else self.depth}."
            elif limit:
                hours=math.ceil(minutes(limit['budget'])/60)
                message=f'ИТЭФ считает дольше ≈{hours} часов М-20. Позиция сохранена.'
            elif self.resigned is not None:message='ИТЭФ признала поражение. Вы выиграли.'
            elif b.is_checkmate():message='Мат. '+('Вы выиграли.' if b.turn!=self.human else 'ИТЭФ выиграла.')
            elif b.is_stalemate():message='Пат. Ничья.'
            elif b.is_game_over():message='Ничья.'
            elif b.turn==self.human:message='Ваш ход.'+(' Шах!' if b.is_check() else '')
            else:message='Ход ИТЭФ.'
            history=[];entries=[];copy=b.root()
            for i,move in enumerate(b.move_stack):
                san=copy.san(move);history.append(san)
                entries.append({'san':san,'move_number':copy.fullmove_number,'color':'white' if copy.turn else 'black',
                                'engine':copy.turn!=self.human,'record':self.records[i]})
                entries[-1]['forced_play']=self.move_forced[i] if i<len(self.move_forced) else 'listing'
                copy.push(move)
            return {'fen':b.fen(),'pieces':{chess.square_name(s):p.symbol() for s,p in b.piece_map().items()},
                    'legal':[m.uci() for m in b.legal_moves],'human':'white' if self.human else 'black',
                    'turn':'white' if b.turn else 'black','busy':self.busy,'error':self.error,
                    'message':message,'history':history,'history_entries':entries,'last':self.last,'depth':self.depth,
                    'budget':self.budget,'limit':limit,'pending':self.pending,'totals':self.totals(),
                    'can_continue':bool(limit and not self.pending.get('exhausted')),
                    'live_resume':self.waiting,
                    'continuation_extra':self.pending.get('base_budget',self.budget) if self.pending else self.budget,
                    'can_reduce':bool(limit and limit['depth']>2 and not self.pending.get('exhausted')),
                    'search_profile':self.machine.search_settings.metadata(),
                    'forced_play':self.machine.forced_play.metadata(),
                    'finished':b.is_game_over() or self.resigned is not None,'last_move':b.peek().uci() if b.move_stack else None}

    def action(self, data):
        depth_override=budget_override=None;retry=False;extend=True
        action=data.get('action')
        with self.lock:
            if self.busy:raise ValueError('Подождите ответа ИТЭФ.')
        if action in ('new','undo','retry'):self.cancel_pause()
        with self.lock:
            if self.busy:raise ValueError('Подождите ответа ИТЭФ.')
            if action=='settings':
                if self.pending and self.pending.get('limit'):
                    raise ValueError('Сначала продолжите расчёт, снизьте глубину или верните ход.')
                depth=int(data.get('depth',self.depth))
                if depth not in (3,4,5):raise ValueError('Глубина должна быть 3, 4 или 5.')
                current=self.machine.forced_play
                forced=ForcedPlay(data.get('forced_variant',current.variant),
                                  data.get('checks_per_side',current.checks_per_side))
                self.depth=depth;self.budget=DEPTH_BUDGETS[depth]
                self.machine.forced_play=forced;self.save();return self.status()
            if action=='new':
                if data.get('side','white') not in ('white','black'):raise ValueError('Неизвестный цвет.')
                depth=int(data.get('depth',self.depth))
                if depth not in (3,4,5):raise ValueError('Глубина должна быть 3, 4 или 5.')
                self.board=chess.Board();self.human=data.get('side','white')=='white';self.depth=depth
                self.budget=DEPTH_BUDGETS[depth]
                self.records=[];self.comments=[];self.move_forced=[];self.pending=None
                self.last=None;self.resigned=None;self.error='';self.save()
            elif action=='move':
                if self.board.is_game_over() or self.resigned is not None:raise ValueError('Партия окончена.')
                if self.board.turn!=self.human:raise ValueError('Сейчас ход ИТЭФ.')
                text=str(data.get('move','')).strip()
                try:move=self.board.parse_uci(text.lower())
                except ValueError:move=self.board.parse_san(text)
                self.board.push(move);self.records.append(None);self.comments.append('')
                self.move_forced.append(None)
                self.last=None;self.pending=None;self.error='';self.save()
            elif action=='undo':
                if self.board.move_stack:self.board.pop();self.records.pop();self.comments.pop();self.move_forced.pop()
                if self.board.move_stack and self.board.turn!=self.human:self.board.pop();self.records.pop();self.comments.pop();self.move_forced.pop()
                self.error='';self.last=None;self.resigned=None;self.pending=None;self.save()
            elif action in ('continue','reduce'):
                limit=self.pending.get('limit') if self.pending else None
                if not limit or self.pending.get('exhausted'):raise ValueError('Нет расчёта, ожидающего продолжения.')
                if action=='reduce' and limit['depth']<=2:raise ValueError('Глубина уже не выше двух полуходов.')
                if self.waiting:
                    self.resume_choice=action;self.busy=True;self.resume_event.set()
                    return self.status()
                # After application restart, replay from the root, not a CPU resume.
                self.pending['replayed']=True
                if action=='continue':
                    depth_override=limit['depth'];budget_override=2*self.pending['base_budget']
                else:
                    depth_override=limit['depth']-1;budget_override=DEPTH_BUDGETS[depth_override]
                retry=True;extend=False
            elif action=='retry':self.error='';retry=True
            else:raise ValueError('Неизвестная команда.')
        self.start_engine(depth_override,budget_override,retry,extend=extend)
        return self.status()

    def pgn(self):
        with self.lock:
            game=chess.pgn.Game.from_board(self.board)
            game.headers['Event']='Партия с ИТЭФ / v19.1'
            forced=self.machine.forced_play
            game.headers['M20ForcedPlay']=forced.variant
            if forced.variant=='checks':game.headers['M20ChecksPerSide']=str(forced.checks_per_side)
            variants=sorted(set(v for v in self.move_forced if v))
            if len(variants)>1:game.headers['M20ForcedPlayHistory']=', '.join(variants)
            settings=self.machine.search_settings
            game.headers['SearchProfile']=settings.profile
            game.headers['SearchChecks']=str(settings.checks)
            game.headers['SearchEvaluations']=str(settings.evaluations)
            game.headers['SearchRankCap']=str(settings.rank_cap)
            game.headers['Search4344']='source' if settings.source_4344 else 'printed'
            game.headers['SearchForcedScheme']=settings.forced_scheme
            game.headers['SearchDepth']=str(self.depth)
            game.headers['M20TerminalRule']='Stanford-2prime-v18'
            game.headers['CommandBudget']=str(self.budget)
            game.headers['M20CommandsPerMinute']=str(COMMANDS_PER_MINUTE)
            totals=self.totals()
            game.headers['M20TotalCommands']=str(totals['steps'])
            game.headers['M20TotalMinutes']=f"{totals['minutes']:.6f}"
            game.headers['M20CompletedCommands']=str(totals['completed_steps'])
            game.headers['M20RecordedMoves']=str(totals['recorded_moves'])
            game.headers['White']='Игрок' if self.human else 'ИТЭФ М-20'
            game.headers['Black']='ИТЭФ М-20' if self.human else 'Игрок'
            for i,node in enumerate(game.mainline()):
                node.comment=self.comments[i]
                if self.records[i]:node.comment=(node.comment+' '+pgn_comment(self.records[i])).strip()
                elif node.parent.board().turn!=self.human and not '[%m20_forced ' in node.comment:
                    tag=self.move_forced[i] if i<len(self.move_forced) else 'listing'
                    node.comment=(node.comment+f' [%m20_forced {tag or "listing"}]').strip()
            if self.pending and self.pending.get('limit'):
                lim=self.pending['limit']
                game.end().comment+=(f" После этой позиции расчёт ответа при глубине {lim['depth']} "
                                     f"остановлен по лимиту {lim['budget']} команд; {format_time(lim['steps'])} М-20; "
                                     f"вариант {ForcedPlay.from_metadata(lim.get('forced_play')).tag()}.")
            if self.resigned is not None:
                game.headers['Result']='0-1' if self.resigned else '1-0'
                game.end().comment+=' ИТЭФ признала поражение: родной поиск вернул нижнюю предельную оценку.'
                if self.last:game.end().comment+=' Расчёт сдачи: '+pgn_comment(self.last)
            return str(game)+'\n'

def serve(port=0, open_browser=True, save=True, machine_options=None, budget=None, pgn_path=None, human=None, depth=None):
    game=Game(ROOT/'game.json' if save else None, machine_options=machine_options, budget=budget, depth=depth)
    if pgn_path:
        game.load_pgn(pgn_path,human)
        options=machine_options or {};current=game.machine.forced_play
        game.machine.forced_play=ForcedPlay(options.get('forced_variant',current.variant),
                                           options.get('checks_per_side',current.checks_per_side))
        if depth is not None:game.depth=depth;game.budget=DEPTH_BUDGETS[depth]
        game.save()
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self, data, content_type='application/json; charset=utf-8', code=200):
            payload=(json.dumps(data,ensure_ascii=False) if isinstance(data,dict) else data).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(payload)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            if self.path=='/':
                self.reply((ROOT/'ui.html').read_text(encoding='utf-8').replace('__TOKEN__',token),'text/html; charset=utf-8')
            elif self.path=='/api/state':self.reply(game.status())
            elif self.path=='/game.pgn':self.reply(game.pgn(),'application/x-chess-pgn; charset=utf-8')
            else:self.reply({'error':'Не найдено'},code=404)
        def do_POST(self):
            if self.path!='/api/action' or self.headers.get('X-Game-Token')!=token:
                self.reply({'error':'Недоступно'},code=403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError('Некорректный размер запроса.')
                data=json.loads(self.rfile.read(size))
                if not isinstance(data,dict):raise ValueError('Некорректная команда.')
                self.reply(game.action(data))
            except (ValueError,TypeError) as e:self.reply({'error':str(e)},code=400)
            except Exception as e:self.reply({'error':str(e)},code=500)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    address=f'http://127.0.0.1:{server.server_port}/'
    print('\nИТЭФ · М-20 · 1966 / v19.1\n'
          +'Профиль: '+game.machine.search_settings.profile+'\n'+address
          +'\nОставьте это окно открытым. Ctrl+C — выход.\n',flush=True)
    game.start_engine()
    if open_browser:webbrowser.open(address)
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nПартия сохранена.' if save else '\nДо встречи.')
    finally:server.server_close()

def main():
    parser=argparse.ArgumentParser(description='ИТЭФ М-20: шахматы из листинга 1966 года')
    parser.add_argument('--think',action='store_true',help='один ответ JSON вместо открытия доски')
    parser.add_argument('--fen',default=chess.STARTING_FEN)
    parser.add_argument('--moves',nargs='*',default=[],help='ходы UCI: e2e4 e7e5')
    parser.add_argument('--depth',type=int,choices=[3,4,5],help='глубина игры; по умолчанию 3 или сохранённая настройка')
    parser.add_argument('--budget',type=int,help='лимит команд; в игре 3000000000 / 10000000000 / 20000000000')
    parser.add_argument('--pgn',type=Path,help='продолжить партию из PGN; заменяет текущее сохранение')
    parser.add_argument('--side',choices=('white','black'),help='цвет игрока при загрузке PGN')
    parser.add_argument('--profile',choices=tuple(PROFILES),default=DEFAULT_PROFILE,
                        help='профиль поиска; по умолчанию '+DEFAULT_PROFILE)
    parser.add_argument('--checks',type=int,choices=range(5),help='лимит шахов 4777 (единица 1<<39)')
    parser.add_argument('--evaluations',type=int,choices=range(1,6),help='лимит оцениваний 1661')
    parser.add_argument('--rank-cap',type=int,choices=(14,16),help='предел абсолютного ранга; 16 с переносом пяти массивов')
    parser.add_argument('--forced-scheme',choices=('native','narrow'),help='форсированный генератор: штатный или только взятия; защиты от шаха сохраняются')
    parser.add_argument('--forced-play',dest='forced_variant',choices=tuple(VARIANTS),help='вариант допуска; без настройки — listing')
    parser.add_argument('--checks-per-side',type=int,choices=range(MAX_CHECKS+1),metavar='N',help='число шахов каждой стороны в варианте checks; по умолчанию 2')
    source_group=parser.add_mutually_exclusive_group()
    source_group.add_argument('--source-4344',dest='source_4344',action='store_true',help='4344 использует 1054 по символической записи')
    source_group.add_argument('--printed-4344',dest='source_4344',action='store_false',help='4344 использует напечатанное 1057')
    parser.set_defaults(source_4344=None)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--no-save',action='store_true')
    args=parser.parse_args()
    machine_options={k:getattr(args,k) for k in ('profile','checks','evaluations','rank_cap','source_4344','forced_scheme')}
    machine_options.update({k:getattr(args,k) for k in ('forced_variant','checks_per_side') if getattr(args,k) is not None})
    if args.think:
        if args.pgn:
            with args.pgn.open(encoding='utf-8-sig') as source:game=chess.pgn.read_game(source)
            if game is None or game.errors:raise ValueError('Не удалось прочитать легальную партию PGN.')
            board=game.end().board()
            forced=ForcedPlay.from_headers(game.headers)
            machine_options.setdefault('forced_variant',forced.variant)
            machine_options.setdefault('checks_per_side',forced.checks_per_side)
        else:board=chess.Board(args.fen)
        for move in args.moves:board.push_uci(move)
        print(json.dumps(Machine(**machine_options).think(board,args.depth or 3,budget=args.budget if args.budget is not None else DEPTH_BUDGETS[args.depth or 3]),ensure_ascii=False,indent=2))
    else:serve(args.port,not args.no_browser,not args.no_save,machine_options=machine_options,
               budget=args.budget,pgn_path=args.pgn,human=args.side,depth=args.depth)

if __name__=='__main__':
    try:main()
    except (MachineError,RuntimeError,ValueError) as e:
        raise SystemExit(str(e))
