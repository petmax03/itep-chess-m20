/* v18: terminal-position rule, Stanford report (2'), (5), printed p. 9.
 * Functional restoration from the report, NOT a claimed transcription of a
 * missing machine-code sheet. The listing's own constants are used:
 * 1074 = 2C+1; 1102 = C+1/2. A mated side to move scores zero; the original
 * minimax at 4100 complements that to 1074 for the winning parent.
 * This recognizer supplies only the chess termination predicate. It does not
 * rank candidates, select a move, extend depth, or evaluate a live position.
 */
static unsigned terminal_enabled=1;
uint64_t itef_terminal_stats[3]; /* inspected, checkmates, stalemates */
void itef_set_terminal(unsigned enabled) { terminal_enabled=enabled!=0; }

static int terminal_try(int b[64],unsigned side,int from,int to,int ep) {
    int piece=b[from],target=b[to],taken=ep>=0?b[ep]:0;
    b[from]=0;b[to]=piece;
    if(ep>=0)b[ep]=0;
    /* All promotions have identical occupancy for own-king safety. */
    int legal=!attacked(b,side);
    b[from]=piece;b[to]=target;
    if(ep>=0)b[ep]=taken;
    return legal;
}

static int terminal_has_move(int b[64],unsigned side) {
    static const int jump[8][2]={{1,2},{2,1},{2,-1},{1,-2},{-1,-2},{-2,-1},{-2,1},{-1,2}};
    static const int ray[8][2]={{1,0},{-1,0},{0,1},{0,-1},{1,1},{1,-1},{-1,1},{-1,-1}};
    for(int from=0;from<64;from++) {
        int p=b[from];if(!p||((p<0)!=(int)side))continue;
        int type=p<0?-p:p,f=from%8,r=from/8;
        if(type==1) {
            int step=side?-1:1,next=r+step;
            if(next<0||next>7)continue;
            int to=next*8+f;
            if(!b[to]) {
                if(terminal_try(b,side,from,to,-1))return 1;
                if(r==(side?6:1)&&!b[(r+2*step)*8+f]&&
                   terminal_try(b,side,from,(r+2*step)*8+f,-1))return 1;
            }
            for(int df=-1;df<=1;df+=2) {
                if(f+df<0||f+df>7)continue;
                to=next*8+f+df;
                if(b[to]&&((b[to]<0)!=(int)side)&&b[to]!=(side?6:-6)) {
                    if(terminal_try(b,side,from,to,-1))return 1;
                } else if(!b[to]&&r==(side?3:4)) {
                    unsigned code=63-to,bit=side?code-32:code;
                    uint64_t mask=M[side?03041:07042];
                    int ep=to-8*step;
                    if(bit<32&&(mask&(1ULL<<bit))&&b[ep]==(side?1:-1)&&
                       terminal_try(b,side,from,to,ep))return 1;
                }
            }
        } else {
            int begin=type==3?4:0,end=type==4?4:8;
            for(int d=begin;d<end;d++) {
                int df=type==2?jump[d][0]:ray[d][0];
                int dr=type==2?jump[d][1]:ray[d][1];
                int ff=f+df,rr=r+dr;
                while(ff>=0&&ff<8&&rr>=0&&rr<8) {
                    int to=rr*8+ff,target=b[to];
                    if(target&&((target<0)==(int)side))break;
                    if(target==(side?6:-6))break;
                    if(terminal_try(b,side,from,to,-1))return 1;
                    if(target||type==2||type==6)break;
                    ff+=df;rr+=dr;
                }
            }
        }
    }
    /* A legal castle implies a legal one-square king move to the transit
     * square, already examined above, so cannot be the sole legal move. */
    return 0;
}

/* Exported read-only predicate for independent rules tests: 0 live, 1 mate,
 * 2 stalemate. No use of python-chess in the engine's terminal decision. */
int itef_terminal_kind(unsigned side) {
    int b[64];read_board(b);
    if(terminal_has_move(b,side))return 0;
    return attacked(b,side)?1:2;
}
static void terminal_before(unsigned pc) {
    if(!terminal_enabled||(pc!=04042&&pc!=04111))return;
    unsigned rank=(M[01700]>>12)&07777;
    if(rank>16)return;
    itef_terminal_stats[0]++;
    int kind=itef_terminal_kind(rank&1);
    if(!kind)return;
    itef_terminal_stats[kind]++;
    /* A terminal node has no candidate list. The early return bypasses
     * native cleanup 4675; stale entries otherwise reach 4231/4255 and
     * request line attacks for a figure absent from this position.
     * Read the array base from the loaded instruction so rank-cap 16's
     * relocation (6520 -> 4710) remains authoritative. */
    unsigned pointer_base=M[04675]&07777;
    M[(pointer_base+rank)&07777]=0;
    M[07460+rank]=kind==1?0:M[01102];
    RVK=pc==04042?04063:04135;
}
