"""Operator budgets and fallback; no changes to native chess decisions."""
from .machine import CommandLimitError
from .telemetry import completed_record

DEPTH_BUDGETS={1:3_000_000_000,2:3_000_000_000,3:3_000_000_000,
               4:10_000_000_000,5:20_000_000_000}

class SearchCancelled(Exception):
    pass

def calculate(machine,board,depth=3,budget=None,*,pause=None,progress=None,
              attempts=(),requested_depth=None,extend=True):
    """B + one B extension at requested depth; then d-1, ... 2 once each.

    pause(exc) returns 'continue' or 'reduce', or raises SearchCancelled.
    Without pause (UCI), the single extension is automatic. Checkpoints inside
    a resumed calculation are not counted again as separate attempts.
    """
    requested_depth=requested_depth or depth
    initial=budget if budget is not None else DEPTH_BUDGETS[depth]
    attempts=list(attempts);fallbacks=[];extensions=[]
    if depth<requested_depth:fallbacks.append(depth)
    for current in range(depth,min(depth,2)-1,-1):
        cap=initial if current==depth else DEPTH_BUDGETS[current]
        extended=False
        def at_limit(exc):
            nonlocal extended
            if current!=depth or extended or not extend:return 0
            decision=pause(exc) if pause else 'continue'
            if decision=='continue':
                extended=True;extensions.append({'depth':current,'extra':cap})
                return cap
            if decision!='reduce':raise SearchCancelled()
            return 0
        if progress:progress(current,attempts)
        try:
            answer=machine.think(board,current,budget=cap,on_limit=at_limit)
            result=completed_record(answer,attempts,requested_depth,cap*(2 if extended else 1))
            result.update(fallback_depths=fallbacks,extensions=extensions)
            return result
        except CommandLimitError as exc:
            attempts.append(exc.measurement())
            if current<=2:
                exc.attempts=attempts;raise
            fallbacks.append(current-1)
