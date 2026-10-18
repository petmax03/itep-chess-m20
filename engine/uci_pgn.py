"""Optional PGN of the UCI line, with the M-20's own measurements and rules."""
from pathlib import Path
from .machine import chess
from .forced_play import ForcedPlay
from .telemetry import pgn_comment, minutes
import chess.pgn


class UCIPGN:
    def __init__(self):
        self.path = None
        self.records = {}

    def clear(self):
        self.records.clear()

    def answer(self, board, result, forced):
        if not result.get('move'):
            return
        board = board.copy()
        board.push_uci(result['move'])
        key = (board.root().fen(), tuple(m.uci() for m in board.move_stack))
        self.records[key] = result
        self.write(board, forced)

    def write(self, board, forced):
        if self.path is None:
            return
        game = chess.pgn.Game.from_board(board)
        game.headers['Event'] = 'ITEF M-20 / UCI v19.1'
        game.headers['M20TerminalRule'] = 'Stanford-2prime-v18'
        game.headers['M20ForcedPlay'] = forced.variant
        if forced.variant == 'checks':
            game.headers['M20ChecksPerSide'] = str(forced.checks_per_side)
        history = []; tags = set(); total = 0; root = board.root().fen()
        for node in game.mainline():
            history.append(node.move.uci())
            record = self.records.get((root, tuple(history)))
            if record:
                node.comment = pgn_comment(record)
                tags.add(ForcedPlay.from_metadata(record.get('forced_play')).tag())
                total += record['total_steps']
                game.headers['White' if node.parent.board().turn else 'Black'] = 'ITEF M-20'
                game.headers['SearchProfile'] = record['search_profile']['name']
                game.headers['SearchDepth'] = str(record['requested_depth'])
        if len(tags) > 1:
            game.headers['M20ForcedPlayHistory'] = ', '.join(sorted(tags))
        game.headers['M20TotalCommands'] = str(total)
        game.headers['M20TotalMinutes'] = f'{minutes(total):.6f}'
        path = Path(self.path)
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(str(game)+'\n', encoding='utf-8')
        temp.replace(path)
