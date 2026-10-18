"""The 1966 ITEF listing running in a 45-bit M-20 interpreter.

python-chess supplies the operator's board and an independent output check.
It does not rank moves or participate in the machine's search.
"""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor"))
import chess
from .build import build
from .castling import native_castling_words
from .search_profiles import DEFAULT_PROFILE, resolve_search_settings, apply_search_settings
from .forced_play import ForcedPlay, VARIANTS
from .promotion_slots import apply_promotion_repair

WORD = (1 << 45) - 1
DEAD = 0o177740000000000

# Octal addresses and words. See docs/RECONSTRUCTION.md for evidence/limits.
BASE_PATCHES = {
    0o2317: 0o455654110453001,  # prose says 6541; printed machine field says 6511
    0o2133: 0o037166700000000,  # FA must read sigma (1667)
    0o2637: 0o455701100130141,  # holes: handwritten intersection, symmetric with 2636
    0o3667: 0o033171610751716,  # change the move, not bishop code at 1216
    0o3705: 0o055170240121665,  # destination mask eta0
    # PDF pp.34 and 37 reuse 4231 for two different routines. Preserve the
    # line routine and relocate the earlier check-evasion tail; see V11_SEARCH.
    0o4172: 0o553742000107420,  # original 4230
    0o4173: 0o016000600073636,  # p.34 4231: set generator mode 6 and return
    0o4226: 0o076000041730000,  # direct branch to the relocated mode-6 return
    0o4230: 0o056000041720000,  # fallthrough via the relocated two-word tail
    0o0106: 0o000600000000000,  # native routines explicitly address 6000/6001
    0o0105: 0o103500000000000,  # normalized number 5, also the promotion type mask
    0o0107: 0o103700000000000,
    0o0110: 0o104400000000000,
    0o0112: 0o104500000000000,  # normalized number 10; its exponent encodes shift +4
    0o0704: 0o016000000070000,  # host displays evaluation, skip printer subroutine
    0o7764: 0o056000000070000,
    0o7775: 1,                 # reconstructed console BO switch
}

# Historical callers import PATCHES; preserve that public name.
PATCHES = BASE_PATCHES


def read_listing(path):
    addr = None
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.split(";", 1)[0].strip()
        if not line:
            continue
        if re.fullmatch(r":[0-7]+", line):
            addr = int(line[1:], 8)
            continue
        if addr is None:
            continue
        fields = line.split()
        if len(fields) == 5 and all(re.fullmatch("[0-7]+", f) for f in fields):
            p, op, a, b, c = [int(f, 8) for f in fields]
            yield addr, (p << 42) | (op << 36) | (a << 24) | (b << 12) | c
        addr += 1


def square(code):
    return chess.square_name(63 - code)


class MachineError(RuntimeError):
    pass


class CommandLimitError(MachineError):
    """A paused operator calculation, with measured work, not a CPU fault."""
    def __init__(self, budget, steps, nodes, pc):
        self.budget, self.steps, self.nodes, self.pc = budget, steps, nodes, pc
        self.depth = None
        self.seconds = 0.0
        self.forced_play = None
        super().__init__(f"Достигнут лимит {budget:,} команд М-20 (адрес {pc:04o}).")

    def __str__(self):
        return f"Достигнут лимит {self.budget:,} команд М-20 (адрес {self.pc:04o})."

    def measurement(self):
        return dict(status='limit', budget=self.budget, steps=self.steps,
                    nodes=self.nodes, depth=self.depth, seconds=self.seconds,
                    pc=f'{self.pc:04o}', forced_play=self.forced_play)


class Machine:
    def __init__(self, castling=True, profile=DEFAULT_PROFILE, *, checks=None,
                 evaluations=None, rank_cap=None, source_4344=None, forced_scheme=None,
                 forced_variant='listing', checks_per_side=2, terminal_rules=True,
                 promotion_repair=True):
        self.terminal_rules=bool(terminal_rules)
        self.promotion_repair=bool(promotion_repair)
        self.forced_play = ForcedPlay(forced_variant, checks_per_side)
        self.search_settings = resolve_search_settings(
            profile, checks=checks, evaluations=evaluations,
            rank_cap=rank_cap, source_4344=source_4344, forced_scheme=forced_scheme)
        self.lib = C.CDLL(str(build()))
        self.lib.itef_run.argtypes = [C.c_int, C.c_int, C.c_uint64]
        self.lib.itef_run.restype = C.c_int64
        self.lib.itef_reset.argtypes = []
        self.lib.itef_reset.restype = None
        self.lib.itef_set_forced.argtypes = [C.c_uint, C.c_uint]
        self.lib.itef_set_forced.restype = None
        self.lib.itef_set_terminal.argtypes = [C.c_uint]
        self.lib.itef_set_terminal.restype = None
        self.mem = (C.c_uint64 * 4096).in_dll(self.lib, "M")
        self.pc = C.c_uint32.in_dll(self.lib, "RVK")
        self.ra = C.c_uint32.in_dll(self.lib, "RA")
        self.castling = castling
        self.base = {}
        for name in ["m20/as/is2.m20", "m20/kaissa/kaissa.m20",
                     "research/low-constants.m20", "research/standard-cells-values.m20"]:
            self.base.update(read_listing(ROOT / name))
        self.base.update(BASE_PATCHES)
        apply_search_settings(self, self.search_settings)
        if self.promotion_repair:
            apply_promotion_repair(self)

    def reset(self):
        self.lib.itef_set_terminal(self.terminal_rules)
        self.lib.itef_set_forced(VARIANTS[self.forced_play.variant], self.forced_play.checks_per_side)
        self.lib.itef_reset()
        for addr, value in self.base.items():
            self.mem[addr] = value
        for addr in range(0o7500, 0o7620):
            self.mem[addr] = 0
        if not self.castling:
            self.mem[0o3535] = 0o016353635360007

    def run(self, entry, end, budget=300_000_000):
        if not isinstance(budget, int) or not 0 < budget < (1 << 63):
            raise ValueError("Лимит команд должен быть целым числом от 1 до 2^63−1.")
        count = self.lib.itef_run(-1 if entry is None else entry, end, budget)
        if count == -9999:
            raise CommandLimitError(budget, budget, int(self.mem[0o1706] & 0o77777777), self.pc.value)
        if count < 0:
            raise MachineError(f"Останов М-20: код {count}, адрес {self.pc.value:04o}.")
        return count

    def subroutine(self, address, ra=0):
        self.ra.value = ra
        self.mem[7] = self.mem[0o2231] = 0o016000060000000
        return self.run(address, 0o6000, 2_000_000)

    def encode(self, board):
        if not board.is_valid():
            raise MachineError("Некорректная шахматная позиция.")
        m = self.mem
        castling_words, unknown_colors = native_castling_words(board)
        self.castling_history = {
            "castling_history_known": not unknown_colors,
            "castling_history_unknown_colors": unknown_colors,
        }
        for base, color in [(0o3000, chess.WHITE), (0o7000, chess.BLACK)]:
            # 3042/7041 and 3044/7044 onwards include original constants.
            for i in range(0o41):
                m[base + i] = 0
            for sq, piece in board.piece_map().items():
                if piece.color != color:
                    continue
                c = 63 - sq
                half = 0 if c >= 32 else 1
                bit = 1 << (c % 32)
                m[base + half] |= bit
                if piece.piece_type == chess.PAWN:
                    m[base + 2 + half] |= bit
            for piece, offsets in [(chess.KING, [0o16]), (chess.QUEEN, [0o20, 0o22]),
                                   (chess.ROOK, [0o24, 0o26]), (chess.BISHOP, [0o30, 0o32]),
                                   (chess.KNIGHT, [0o34, 0o36])]:
                squares = sorted(board.pieces(piece, color), reverse=(piece == chess.ROOK))
                if len(squares) > len(offsets):
                    raise MachineError("Эта позиция превышает число слотов фигур в историческом формате.")
                # A rook with a remaining castling right must retain its original slot.
                if piece == chess.ROOK:
                    home = 0 if color else 56
                    if board.has_kingside_castling_rights(color) and home + 7 in squares:
                        rest = [s for s in squares if s != home + 7]
                        squares = [home + 7, (rest[0] if rest else None)]
                    elif board.has_queenside_castling_rights(color) and home in squares:
                        rest = [s for s in squares if s != home]
                        squares = [(rest[0] if rest else None), home]
                for i, off in enumerate(offsets):
                    sq = squares[i] if i < len(squares) else None
                    kind = {chess.KING: 7, chess.QUEEN: 6, chess.ROOK: 5,
                            chess.BISHOP: 4, chess.KNIGHT: 3}[piece]
                    m[base + off] = ((63 - sq) << 36) | (kind << 32) if sq is not None else DEAD
            m[base + 0o40] = castling_words[color]
        m[0o3041] = m[0o7042] = 0
        if board.ep_square is not None:
            c = 63 - board.ep_square
            if board.turn == chess.BLACK:
                m[0o3041] = 1 << (c - 32)
            else:
                m[0o7042] = 1 << c

    def decode(self):
        pieces = {}
        for base, color in [(0o3000, chess.WHITE), (0o7000, chess.BLACK)]:
            for half in [0, 1]:
                bits = self.mem[base + 2 + half] & ((1 << 32) - 1)
                for b in range(32):
                    if bits >> b & 1:
                        pieces[63 - (b + 32 * (1-half))] = chess.Piece(chess.PAWN, color)
            for off, kind in [(0o16, chess.KING), (0o20, chess.QUEEN), (0o22, chess.QUEEN),
                              (0o24, chess.ROOK), (0o26, chess.ROOK), (0o30, chess.BISHOP),
                              (0o32, chess.BISHOP), (0o34, chess.KNIGHT), (0o36, chess.KNIGHT)]:
                w = self.mem[base + off]
                coord = w >> 36 & 127
                if not w & (1 << 35) and coord < 64:
                    pieces[63-coord] = chess.Piece(kind, color)
        return pieces

    def prepare(self, board, depth):
        self.reset()
        self.encode(board)
        side = 0 if board.turn else 1
        m = self.mem
        # Native 5042 toggles the side; prepare the operator's input accordingly.
        m[0o1700] = m[0o1676] = (1-side) << 12
        self.subroutine(0o2234, 1-side)
        m[0o5063] = m[0o5064] = depth << 12
        m[0o6200] = 0o177777777777777
        return side

    def think(self, board, depth=3, budget=3_000_000_000, on_limit=None):
        if board.is_game_over():
            raise MachineError("Партия уже окончена.")
        if depth not in (1, 2, 3, 4, 5):
            raise ValueError("Глубина должна быть от 1 до 5 полуходов.")
        if type(budget) is not int or not 0 < budget < (1 << 63):
            raise ValueError("Лимит команд должен быть положительным целым числом меньше 2^63.")
        side=self.prepare(board, depth)
        m=self.mem
        start = time.monotonic()
        spent = 0
        prior_nodes = 0
        paused_seconds = 0.0

        def elapsed():
            return round(time.monotonic()-start-paused_seconds,3)

        def bounded_run(entry, end, phase_cap=None):
            # Only the operator's budget changes. Native instructions, bounds,
            # move order, weights, and the historical aspiration retry are intact.
            nonlocal spent,budget,paused_seconds
            segment_steps=0
            while True:
                remaining=budget-spent
                phase_remaining=phase_cap-segment_steps if phase_cap else remaining
                allowance=min(remaining,phase_remaining)
                try:
                    if allowance<=0:
                        raise CommandLimitError(0,0,int(m[0o1706]&0o77777777),self.pc.value)
                    count=self.run(entry,end,allowance)
                except CommandLimitError as exc:
                    if phase_cap and phase_remaining<=remaining:
                        raise MachineError(f"Останов служебной процедуры М-20: адрес {exc.pc:04o}.") from exc
                    consumed=exc.steps
                    spent+=consumed;segment_steps+=consumed
                    exc.steps=spent;exc.budget=budget;exc.nodes+=prior_nodes
                    exc.depth=depth;exc.seconds=elapsed();exc.forced_play=self.forced_play.metadata()
                    if on_limit is None:raise
                    pause_start=time.monotonic()
                    try:extra=on_limit(exc)
                    finally:paused_seconds+=time.monotonic()-pause_start
                    if not extra:raise
                    if type(extra) is not int or extra<0 or budget+extra>=(1<<63):
                        raise ValueError('Некорректное продление лимита.')
                    budget+=extra
                    if consumed:entry=None
                    continue
                spent+=count
                return segment_steps+count
        # 5022 dispatches terminal announcements to the absent operator printer.
        # Search has returned here; the selected Lambda is extracted at 5023.
        steps = bounded_run(0o5005, 0o5022)
        nodes = m[0o1706] & 0o77777777
        best = m[0o7520 + side]
        search_mode='original_window'
        if not best:
            # Operator-level recovery for an aspiration search with no principal
            # move. Both searches still execute the original minimax/evaluation.
            # Bounds are complementary nonnegative scores. Zero in both lower
            # bound slots opens the entire score interval. No host move scoring.
            prior_nodes = nodes
            self.prepare(board,depth)
            steps += bounded_run(0o5005,0o5230)
            m[0o7456+side]=m[0o7457+side]=0
            steps += bounded_run(0o5230,0o5231)
            steps += bounded_run(0o5231,0o5232,100_000)
            nodes += m[0o1706] & 0o77777777
            best=m[0o7520+side]
            search_mode='wide_window_retry'
        if not best:
            if search_mode=='wide_window_retry' and m[0o7460+side]==0:
                # At the absolute lower score, strict minimax comparison need
                # not store a move. Expose the native loss score as resignation.
                return {"move":None,"san":None,"resign":True,"reason":"native_loss_score",
                        "nodes":nodes,"steps":steps,"seconds":elapsed(),
                        "depth":depth,"word":"000000000000000","search_mode":search_mode,
                        "lambda_final_1706":m[0o1706] & 0o77777777,
                        "search_profile":self.search_settings.metadata(),
                        "forced_play":self.forced_play.metadata(),
                        **self.castling_history}
            raise MachineError("Родной поиск вернулся без выбранного хода.")
        steps += bounded_run(0o5023, 0o5027, 100_000)
        kind = m[0o1006] >> 12 & 0o37
        if kind >= 0o36:
            row = "1" if board.turn else "8"
            uci = "e" + row + ("g" if kind == 0o36 else "c") + row
        else:
            packed = m[0o5211] >> 12 & 0o7777
            uci = square(packed >> 6) + square(packed & 63)
            if board.piece_type_at(chess.parse_square(uci[:2])) == chess.PAWN and uci[3] in "18":
                uci += "q"
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise MachineError(f"Проверка обнаружила незаконный ответ М-20: {uci}.")
        expected = board.copy()
        expected.push(move)
        if self.decode() != expected.piece_map():
            raise MachineError(f"Ход {uci}: доска М-20 не совпала с контрольной доской.")
        return {"move": uci, "san": board.san(move), "nodes": nodes, "steps": steps,
                "seconds": elapsed(), "depth": depth,
                "word": f"{best:015o}", "search_mode":search_mode,
                "lambda_final_1706":m[0o1706] & 0o77777777,
                "search_profile":self.search_settings.metadata(),
                "forced_play":self.forced_play.metadata(),
                **self.castling_history}
