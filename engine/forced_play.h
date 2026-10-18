/* Opt-in admission rules from v15/report_hooks.c (Stanford §4).
 * No evaluation, minimax, sorting, CPU, or listing edits. Mode 0 bypasses this
 * entirely. The two counters follow the current branch, not the whole tree.
 */
#include "forced_board.h"
#define FORCED_RANKS 128
static unsigned forced_variant, forced_limit=2, forced_base, forced_pass;
static uint64_t forced_checks[FORCED_RANKS][2], forced_bound[FORCED_RANKS];
uint64_t itef_forced_stats[4]; /* considered, admitted, rejected, check moves */

void itef_set_forced(unsigned variant, unsigned limit) {
    forced_variant=variant; forced_limit=limit;
}
static void forced_reset(void) {
    forced_base=forced_pass=0;
    memset(forced_checks,0,sizeof(forced_checks));
    memset(forced_bound,0,sizeof(forced_bound));
    memset(itef_forced_stats,0,sizeof(itef_forced_stats));
}
static unsigned forced_start(void) {
    return forced_pass ? ((M[01740]>>12)&07777) : forced_base+1;
}
static int forced_admit(unsigned rank) {
    unsigned start=forced_start();
    if(rank<start)return 1;
    unsigned ptr=(M[01677]>>12)&07777, side=rank&1;
    int capture,check,incheck,material;
    classify_candidate(M[ptr],side,&capture,&check,&incheck,&material);
    int floor=(forced_bound[rank]&M[02611])>>24;
    uint64_t used=forced_checks[rank][side]-forced_checks[start][side];
    int narrow=forced_variant==1 || (forced_variant==2 && used>=forced_limit);
    int allowed=narrow ? (capture && material>=floor)
                       : (check || ((capture || incheck) && material>=floor));
    itef_forced_stats[0]++;
    itef_forced_stats[allowed?1:2]++;
    return allowed;
}
static int forced_before(unsigned pc) {
    unsigned rank=(M[01700]>>12)&07777;
    if(rank>=FORCED_RANKS)return 1;
    if(pc==05503 || pc==05230) {
        forced_base=rank;
        memset(forced_checks,0,sizeof(forced_checks));
        if(pc==05230)forced_pass++;
    }
    if(pc==02147) {
        forced_bound[rank]=M[07460+rank];
        /* Explicit variants use native captures+checks even when the selected
         * research profile previously requested mode 2. Mode 6 (evasions) stays.
         * Nominal ranks and their candidate order are left alone. */
        if(rank>=forced_start() && ((M[03636]>>12)&07777)==2)
            M[03636]=(M[03636]&~(07777ULL<<12))|(3ULL<<12);
    }
    if(pc==02213 && !forced_admit(rank)) {
        RVK=02205;RA=rank;return 0;
    }
    if(pc==02225 && OMEGA && rank+1<FORCED_RANKS) {
        forced_checks[rank+1][0]=forced_checks[rank][0];
        forced_checks[rank+1][1]=forced_checks[rank][1];
        unsigned check=report_board_check(1-(rank&1));
        forced_checks[rank+1][rank&1]+=check;
        itef_forced_stats[3]+=check;
    }
    return 1;
}
