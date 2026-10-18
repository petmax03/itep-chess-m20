"""Diagnostic access to the listing's generator and move application."""
import ctypes as C
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.machine import Machine, chess, square

def snapshot(machine):
    names = ['RVK', 'RA', 'OMEGA', 'RK', 'RR', 'RMR']
    regs = {n: (C.c_uint32 if n in names[:3] else C.c_uint64).in_dll(machine.lib,n)
            for n in names}
    return bytes(machine.mem), {n:r.value for n,r in regs.items()}

def restore(machine, state):
    C.memmove(C.addressof(machine.mem), state[0], len(state[0]))
    for n,v in state[1].items():
        (C.c_uint32 if n in ['RVK','RA','OMEGA'] else C.c_uint64).in_dll(machine.lib,n).value=v

def generated(machine, board):
    machine.reset(); machine.encode(board)
    m=machine.mem; side=0 if board.turn else 1
    m[0o1700]=m[0o1676]=side<<12
    m[0o1740]=3<<12; m[0o6517+side]=0o6000; m[0o5455]=(1<<36)-1
    machine.subroutine(0o1465,side)
    machine.subroutine(0o7704,side)
    pointer=m[0o6520+side]; begin=pointer>>24&0o7777; end=pointer&0o7777
    assert 0o6000<=begin<=end<0o6517, (oct(begin),oct(end))
    state=snapshot(machine); out={}
    for i in range(begin,end):
        restore(machine,state); m[0o1677]=i<<12
        machine.subroutine(0o1504,side)
        kind=m[0o1006]>>12&0o37
        if kind>=0o36:
            row='1' if board.turn else '8'
            uci='e'+row+('g' if kind==0o36 else 'c')+row
        else:
            machine.subroutine(0o5162)
            packed=m[0o160]>>12&0o7777
            uci=square(packed>>6)+square(packed&63)
            if board.piece_type_at(chess.parse_square(uci[:2]))==chess.PAWN and uci[3] in '18':uci+='q'
        out[uci]=machine.decode()
    restore(machine,state)
    return out
