"""Check source semantics and the wide command-budget ABI, not historic answers."""
import ctypes as C
import json
from native import Machine, chess, snapshot, restore

m=Machine();m.reset()
# More than 2^32 commands allowed, but only two no-ops are executed. A truncated
# uint32 budget becomes 1 and fails; this tests the ABI without billions of steps.
m.mem[0o6000]=m.mem[0o6001]=0o075000000000000
assert m.run(0o6000,0o6002,2**32+1)==2
try:
    m.run(4096,0,10)
except RuntimeError:
    pass
else:
    raise AssertionError('Out-of-memory PC must be an error, not a positive count')
for bad in (0,-1,2**63,1.5):
    try:m.run(0,0,bad)
    except ValueError:pass
    else:raise AssertionError(('invalid budget',bad))
# The source's own branch clearing is restored; no extra child-pointer clear.
m.reset();assert m.mem[0o4675]==0o156000000106520 and m.mem[0o4676]==0
m.prepare(chess.Board(),3);steps=m.run(0o5005,0o4226)
state=snapshot(m);omega=C.c_uint32.in_dll(m.lib,'OMEGA');results=[]
for branch,depth,flag in [('depth_one',1,0),('depth_two',2,1)]:
    branches={}
    for variant in ('v10','printed_tail','v11'):
        restore(m,state);m.mem[0o4024]=depth<<12;omega.value=flag
        if variant!='v11':
            m.mem[0o4226]=0o076000042310000
            m.mem[0o4230]=0o553742000107420
        if variant=='printed_tail':m.mem[0o4231]=0o016000600073636
        before=m.decode();count=m.run(0o4226,0o4337,2_000_000)
        n=m.mem[0o1700]>>12
        branches[variant]={'mode':f'{m.mem[0o3636]:015o}','omega':omega.value,
                           'evaluation':f'{m.mem[0o7420+n]:015o}',
                           'board_unchanged':m.decode()==before,'steps':count}
    for key in ('mode','omega','evaluation','board_unchanged'):
        assert branches['v11'][key]==branches['printed_tail'][key],(branch,key,branches)
    assert branches['v11']['mode']=='016000000060000'
    assert branches['v10']['mode']!=branches['v11']['mode']
    assert branches['v11']['board_unchanged']
    results.append({'branch':branch,'variants':branches})
print(json.dumps({'bridge64':'passed','source_tail':'passed','steps_to_branch':steps,'cases':results},indent=2))
