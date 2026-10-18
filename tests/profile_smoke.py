#!/usr/bin/env python3
"""Four focused CLI checks; no full historical benchmark."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.machine import Machine,read_listing,BASE_PATCHES

def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True)
    a=p.parse_args();baseline=json.loads(a.baseline.read_text())
    original={}
    for name in ['m20/as/is2.m20','m20/kaissa/kaissa.m20','research/low-constants.m20','research/standard-cells-values.m20']:
        original.update(read_listing(ROOT/name))
    original.update(BASE_PATCHES)
    assert Machine(profile='v11').base==original, 'v11 base differs from preserved baseline'
    rows=[]
    for game,num in [(1,16),(2,22)]:
        b=next(r for r in baseline if r['game']==game and r['move_number']==num)
        for profile in ['v11','v12-source']:
            command=[sys.executable,str(ROOT/'play.py'),'--think','--profile',profile,'--depth','3','--fen',b['fen']]
            run=subprocess.run(command,capture_output=True,text=True,check=True,timeout=60)
            result=json.loads(run.stdout)
            assert result['search_profile']['name']==profile
            final_lambda=result['lambda_final_1706']
            aggregate=result['nodes']
            assert type(final_lambda) is int and final_lambda>=0
            assert type(aggregate) is int and aggregate>=final_lambda
            if result['search_mode']=='original_window':
                assert aggregate==final_lambda
            # A retry's nodes sum two searches. Never use that sum as historical lambda.
            if profile=='v11':
                assert (result['move'],result['nodes'],result['word'])==(b['move'],b['nodes'],b['word'])
            rows.append({'game':game,'move_number':num,'profile':profile,
                         'lambda_final':final_lambda,'nodes_host_aggregate':aggregate,'result':result})
            print(json.dumps({'game':game,'move_number':num,'profile':profile,'move':result['move'],'nodes':result['nodes'],'lambda_final_1706':result['lambda_final_1706']},ensure_ascii=False),flush=True)
    report={'v11_base_words_identical':True,
            'counter_contract':{'historical_lambda':'result.lambda_final_1706',
                                'host_aggregate':'result.nodes; includes retries'},
            'cli_runs':rows}
    (ROOT/'test-results/v12-profile-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
