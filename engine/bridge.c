#include "m20_defs.h"
#include <stdint.h>
extern t_value M[], RK, RK_inject, RR, RMR;
extern uint32 RVK, RA, OMEGA;
extern int RK_inject_flag;
extern t_stat cpu_one_inst(void);
#include "forced_play.h"
#include "terminal.h"
int64_t itef_run(int entry,int end,uint64_t budget) {
    uint64_t i; int r;
    /* Negative entry resumes the exact paused CPU, including injected RK. */
    if(entry>=0) {RVK=entry; RK_inject_flag=0;}
    for(i=0;i<budget;i++) {
        if(RVK==(uint32)end && !RK_inject_flag) return i;
        if(RVK>=MEMSIZE) return -10000-(int64_t)RVK;
        if(!RK_inject_flag) terminal_before(RVK);
        if(forced_variant && !RK_inject_flag && !forced_before(RVK)) continue;
        if(RK_inject_flag) {RK=RK_inject; RK_inject_flag=0;}
        else RK=M[RVK++];
        r=cpu_one_inst(); if(r) return -r;
    }
    return -9999;
}
void itef_reset(void) {
    memset(M,0,sizeof(t_value)*MEMSIZE);
    RVK=RA=OMEGA=0; RK=RR=RMR=RK_inject=0;RK_inject_flag=0;
    forced_reset();
    memset(itef_terminal_stats,0,sizeof(itef_terminal_stats));
}
