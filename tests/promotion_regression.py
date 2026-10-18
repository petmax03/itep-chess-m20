#!/usr/bin/env python3
"""Preserve native piece identities across promotion/capture/promotion.

Re-encoding a FEN between moves would hide the original fault.
"""
import ctypes as C
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.machine import Machine, chess, square
from engine.promotion_slots import PATCH
from engine.search_profiles import PROFILES

REGS = {'RVK': C.c_uint32, 'RA': C.c_uint32, 'OMEGA': C.c_uint32,
        'RK': C.c_uint64, 'RR': C.c_uint64, 'RMR': C.c_uint64,
        'RK_inject': C.c_uint64, 'RK_inject_flag': C.c_int}


def snapshot(machine):
    return bytes(machine.mem), {n:t.in_dll(machine.lib, n).value for n,t in REGS.items()}


def restore(machine, state):
    C.memmove(C.addressof(machine.mem), state[0], len(state[0]))
    for n, v in state[1].items():
        REGS[n].in_dll(machine.lib, n).value = v


def apply_native(machine, board, uci):
    assert chess.Move.from_uci(uci) in board.legal_moves, (board.fen(), uci)
    m = machine.mem
    side = 0 if board.turn else 1
    m[0o1700] = m[0o1676] = side << 12
    m[0o1740] = 3 << 12
    pointer_base = 0o4710 if machine.search_settings.rank_cap == 16 else 0o6520
    m[pointer_base - 1 + side] = 0o6000
    m[0o5455] = (1 << 36) - 1
    machine.subroutine(0o1465, side)
    machine.subroutine(0o7704, side)
    pointer = m[pointer_base + side]
    begin, end = pointer >> 24 & 0o7777, pointer & 0o7777
    assert 0o6000 <= begin <= end < 0o6517
    initial = snapshot(machine)
    for i in range(begin, end):
        restore(machine, initial)
        m[0o1677] = i << 12
        machine.subroutine(0o1504, side)
        applied = snapshot(machine)
        kind = m[0o1006] >> 12 & 0o37
        if kind >= 0o36:
            rank = '1' if board.turn else '8'
            candidate = 'e' + rank + ('g' if kind == 0o36 else 'c') + rank
        else:
            machine.subroutine(0o5162)
            packed = m[0o160] >> 12 & 0o7777
            candidate = square(packed >> 6) + square(packed & 63)
            if board.piece_type_at(chess.parse_square(candidate[:2])) == chess.PAWN and candidate[3] in '18':
                candidate += 'q'
        if candidate == uci:
            restore(machine, applied)
            board.push_uci(uci)
            return machine.decode() == board.piece_map()
    raise AssertionError(('Native candidate not found', uci, board.fen()))


def main():
    rows = []
    start = chess.Board('1r2k3/P6P/8/8/8/8/8/3QK3 w - - 0 1')
    sequence = ['a7a8q', 'b8a8', 'h7h8q']
    for profile in PROFILES:
        for color, initial, moves in [('white', start, sequence),
                ('black', start.mirror(), [chess.Move(chess.square_mirror(chess.Move.from_uci(u).from_square),
                    chess.square_mirror(chess.Move.from_uci(u).to_square), promotion=chess.Move.from_uci(u).promotion).uci() for u in sequence])]:
            for enabled in (False, True):
                machine = Machine(profile=profile, promotion_repair=enabled)
                machine.reset(); board = initial.copy(); machine.encode(board)
                matches = [apply_native(machine, board, u) for u in moves]
                assert matches == ([True, True, True] if enabled else [True, True, False]), matches
                if enabled:
                    assert all(machine.mem[a] == w for a,w in PATCH.items())
                rows.append(dict(profile=profile, color=color, repair=enabled,
                                 moves=moves, position_matches=matches, final_fen=board.fen()))
    dest = ROOT / 'test-results/v19.1/promotion-regression.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(rows, indent=2))
    print(f'PASS: {len(rows)} native sequences; both colors; all profiles; original failure reproduced.')


if __name__ == '__main__':
    main()
