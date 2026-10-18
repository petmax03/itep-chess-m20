"""Documented repair of promotion storage, not a recovered manuscript word.

The unmodified instruction at 1604 copies the primary queen to the spare
slot even when that primary queen has been captured. A surviving spare
queen then vanishes from the piece table, but not from the occupancy map.
Execute the original copy only for a live primary queen. All words below
are ordinary M-20 instructions and count towards the command budget.
"""

ORIGINAL = 0o375000030203022
PATCH = {
    0o1604: 0o056000003000000,  # jump to the repair
    0o0300: 0o455302003040000,  # primary queen AND existence/dead bit, indexed by side
    0o0301: 0o076000016050000,  # dead primary: retain the spare, create the new primary
    0o0302: ORIGINAL,          # live primary: original copy to the spare
    0o0303: 0o056000016050000,  # resume the original promotion routine
    0o0304: 1 << 35,
}


def apply_promotion_repair(machine):
    assert machine.base[0o1604] == ORIGINAL, 'Unexpected promotion instruction'
    assert all(a not in machine.base for a in range(0o300, 0o305)), 'Overlay space occupied'
    machine.base.update(PATCH)
