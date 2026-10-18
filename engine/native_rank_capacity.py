"""Native memory-capacity patch, audited against v11. No host move scoring.

Addresses/words are octal. All five rank arrays are relocated together. This
supports the original absolute rank cap through decimal16; it does not change
4130/4131 recursion, 4344 selection, generator modes, or evaluation. Slots19
per line include read-ahead by two. Twenty pointer slots include parent-2 and
child+1. Snapshot capacity is unchanged: generation ends before rank16 and
sixteen10-word slots6540..6777 fit below the working board7000.

This memory-layout repair is a reconstruction, not proof of the match's cap.
"""
POINTER_BASE = 0o4710
LINE_BASES = {0o7320:0o4434, 0o7340:0o4457, 0o7360:0o4502, 0o7400:0o4525}
REGIONS = {"pointers": (0o4706,0o4731), "line_7320": (0o4434,0o4456),
           "line_7340": (0o4457,0o4501), "line_7360": (0o4502,0o4524),
           "line_7400": (0o4525,0o4547)}
# Explicit word assertions prevent accidentally rewriting masks or unrelated data.
RELOCATIONS = {
    0o0700: (0o555652001356520, 0o555471001354710),
    0o0723: (0o000652000006517, 0o000471000004707),
    0o2147: (0o314013065176520, 0o314013047074710),
    0o2150: (0o455651701311704, 0o455470701311704),
    0o2152: (0o313170465206520, 0o313170447104710),
    0o2171: (0o417652017060000, 0o417471017060000),
    0o2205: (0o214013065200010, 0o214013047100010),
    0o2206: (0o233001065200000, 0o233001047100000),
    0o2210: (0o214006465201677, 0o214006447101677),
    0o2211: (0o513652001246520, 0o513471001244710),
    0o2227: (0o555652001356520, 0o555471001354710),
    0o2230: (0o575652010066520, 0o575471010064710),
    0o3540: (0o214005065201663, 0o214005047101663),
    0o3572: (0o257300065170000, 0o257300047070000),
    0o4054: (0o200170665170000, 0o200170647070000),
    0o4105: (0o556652046427520, 0o556471046427520),
    0o4127: (0o200170665170000, 0o200170647070000),
    0o4165: (0o214006465167776, 0o214006447067776),
    0o4221: (0o214006465177776, 0o214006447077776),
    0o4231: (0o275000065214016, 0o275000047114016),
    0o4234: (0o475732240200010, 0o475443640200010),
    0o4235: (0o475734240210011, 0o475446140210011),
    0o4236: (0o475736240220012, 0o475450440220012),
    0o4237: (0o475740240230013, 0o475452740230013),
    0o4240: (0o575732000107320, 0o575443400104434),
    0o4241: (0o575734000117340, 0o575445700114457),
    0o4242: (0o575736000127360, 0o575450200124502),
    0o4243: (0o575740000137400, 0o575452500134525),
    0o4245: (0o175000000007320, 0o175000000004434),
    0o4246: (0o175000000007340, 0o175000000004457),
    0o4247: (0o175000000007360, 0o175000000004502),
    0o4250: (0o156000000077400, 0o156000000074525),
    0o4255: (0o275000065214016, 0o275000047114016),
    0o4630: (0o214013065170012, 0o214013047070012),
    0o4636: (0o133652000120000, 0o133471000120000),
    0o4642: (0o233000065200000, 0o233000047100000),
    0o4675: (0o156000000106520, 0o156000000104710),
    0o5056: (0o114005001066517, 0o114005001064707),
    0o5156: (0o113000001036520, 0o113000001034710),
    0o5471: (0o476652054730011, 0o476471054730011),
    0o5472: (0o433652001245456, 0o433471001245456),
    0o5474: (0o176545654776520, 0o176545654774710),
    0o5476: (0o113001001066520, 0o113001001064710),
    0o5520: (0o455651701311663, 0o455470701311663),
    0o5521: (0o455652001311704, 0o455471001311704),
    0o5561: (0o215001065170011, 0o215001047070011),
    0o5564: (0o455651755710011, 0o455470755710011),
    0o5637: (0o433652057070000, 0o433471057070000),
    0o5645: (0o433652001240011, 0o433471001240011),
    0o5654: (0o456652056615627, 0o456471056615627),
    0o5655: (0o533652001246520, 0o533471001244710),
    0o5700: (0o214011465170011, 0o214011447070011),
}

def apply_native_rank_capacity(machine, cap=14):
    """Apply before prepare/reset; return exact edited words for a run manifest."""
    if type(cap) is not int or not 0 <= cap <= 16:
        raise ValueError("Native rank-cap memory layout supports decimal0..16")
    for address, (old, new) in RELOCATIONS.items():
        value = machine.base.get(address, 0)
        if value not in (old, new):
            raise ValueError(f"Unexpected native word at {address:04o}: {value:015o}")
    for name, (first,last) in REGIONS.items():
        for address in range(first,last+1):
            if machine.base.get(address,0):
                raise ValueError(f"Reserved {name} cell {address:04o} is occupied")
    for address, (_, new) in RELOCATIONS.items():
        machine.base[address] = new
    word = machine.base[0o4120]
    if word & ~(0o7777<<24) != 0o112000041220000:
        raise ValueError("Unexpected rank-limit instruction at4120")
    machine.base[0o4120] = (word & ~(0o7777<<24)) | (cap<<24)
    return {f"{a:04o}":f"{machine.base[a]:015o}" for a in (*RELOCATIONS,0o4120)}
