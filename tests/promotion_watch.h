/* Test-only board/piece-table invariant; never linked into the release. */
uint64_t audit_count=0,audit_fail=0,audit_rows[256][96];
static int audit_board(unsigned pc) {
    if(RK_inject_flag || !(pc==01504||pc==02220||pc==02234||pc==02345))return 0;
    uint64_t *r=audit_rows[(audit_count++)%256];
    r[0]=pc;r[1]=RA;r[2]=M[01700];r[3]=M[01006];r[4]=M[01007];r[5]=M[01706];r[6]=M[01677];r[7]=M[01667];
    for(unsigned i=0;i<041;i++){r[8+i]=M[03000+i];r[41+i]=M[07000+i];}
    r[74]=M[01740];r[75]=M[01676];r[76]=M[01704];r[77]=M[0007];r[78]=M[01700+1];
    unsigned bad=0;
    for(unsigned side=0;side<2;side++) {
        unsigned base=side?07000:03000;
        uint64_t occupied[2]={M[base+2]&0xffffffffULL,M[base+3]&0xffffffffULL};
        for(unsigned off=016;off<=036;off+=2) {
            uint64_t w=M[base+off];unsigned co=(w>>36)&0177;
            if(w&(1ULL<<35)||co>=64)continue;
            unsigned half=co>=32?0:1;uint64_t bit=1ULL<<(co%32);
            if(occupied[half]&bit)bad|=(4<<side);
            occupied[half]|=bit;
        }
        if(occupied[0]!=(M[base]&0xffffffffULL)||occupied[1]!=(M[base+1]&0xffffffffULL))bad|=(1<<side);
        r[80+2*side]=occupied[0];r[81+2*side]=occupied[1];
    }
    r[79]=bad;
    if(bad){audit_fail=bad;return 1;}
    return 0;
}

