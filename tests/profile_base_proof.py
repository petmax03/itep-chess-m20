#!/usr/bin/env python3
"""Compare all 4096 memory words with matrix configurations without searching."""
import argparse,ast,hashlib,json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from engine.machine import Machine,read_listing

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def base_from_snapshot(folder):
    image={}
    for name in ['m20/as/is2.m20','m20/kaissa/kaissa.m20','research/low-constants.m20','research/standard-cells-values.m20']:
        image.update(read_listing(folder/name))
    tree=ast.parse((folder/'engine/machine.py').read_text())
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PATCHES' for t in n.targets))
    image.update(ast.literal_eval(assignment.value))
    return image

def compare(actual,expected):
    differences=[{'address':f'{a:04o}','actual':f'{actual.get(a,0):015o}','expected':f'{expected.get(a,0):015o}'} for a in range(4096) if actual.get(a,0)!=expected.get(a,0)]
    assert not differences,differences
    assert actual==expected,'Effective words match but dictionary entries differ'
    def digest(image):return hashlib.sha256(b''.join(image.get(a,0).to_bytes(8,'little') for a in range(4096))).hexdigest()
    return {'addresses_compared':4096,'dictionary_equal':True,'actual_sha256':digest(actual),'expected_sha256':digest(expected),'differences':differences,'expected_words':{f'{a:04o}':f'{expected.get(a,0):015o}' for a in range(4096)}}

def main():
    p=argparse.ArgumentParser();p.add_argument('--cap16-matrix',type=Path,required=True);p.add_argument('--generator-matrix',type=Path,required=True);p.add_argument('--smoke-narrow',action='store_true');a=p.parse_args()
    cap=a.cap16_matrix;gen=a.generator_matrix
    capmanifest=json.loads((cap/'manifest.json').read_text());genmanifest=json.loads((gen/'manifest.json').read_text())
    capbaseline=cap/'engine-baseline';genbaseline=gen/'engine-baseline'
    for folder,manifest in [(capbaseline,capmanifest),(genbaseline,genmanifest)]:
        for name,digest in manifest['source_sha256'].items():assert sha(folder/name)==digest,name
    expected=base_from_snapshot(capbaseline);namespace={};exec(compile((cap/'native_rank_capacity.py').read_text(),str(cap/'native_rank_capacity.py'),'exec'),namespace)
    namespace['apply_native_rank_capacity'](SimpleNamespace(base=expected),cap=16)
    config=next(c for c in capmanifest['configurations'] if c['id']=='cap16_formula_c0_e3')
    expected.update({int(k,8):int(v,8) for k,v in config['patches'].items()})
    source=compare(Machine(profile='v12-source').base,expected)
    source['matrix_configuration']=config['id']
    expected=base_from_snapshot(genbaseline)
    config=next(c for c in genmanifest['configurations'] if c['id']=='generator_narrow_printed_c0_e3_cap14')
    expected.update({int(k,8):int(v,8) for k,v in config['patches'].items()})
    narrow=compare(Machine(profile='v12-narrow').base,expected);narrow['matrix_configuration']=config['id']
    old=compare(Machine(profile='v11').base,base_from_snapshot(capbaseline))
    hashes={}
    for name in ['m20/kaissa/kaissa.m20','m20/simh/m20_cpu.c','m20/simh/m20_defs.h','engine/bridge.c']:
        hashes[name]={'engine':sha(ROOT/name),'cap16_matrix':sha(capbaseline/name),'generator_matrix':sha(genbaseline/name)}
        assert len(set(hashes[name].values()))==1,name
    capacity={'engine':sha(ROOT/'engine/native_rank_capacity.py'),'matrix':sha(cap/'native_rank_capacity.py'),'manifest':capmanifest['capacity_patch_sha256']}
    assert len(set(capacity.values()))==1
    invalid=[]
    for args in [('--checks','5'),('--evaluations','0'),('--rank-cap','15'),('--forced-scheme','unknown'),('--source-4344','--printed-4344')]:
        r=subprocess.run([sys.executable,str(ROOT/'play.py'),'--think',*args],capture_output=True,text=True,timeout=10)
        assert r.returncode==2 and not r.stdout
        invalid.append({'arguments':list(args),'returncode':r.returncode,'stderr':r.stderr})
    report={'no_search_in_base_comparison':True,'profiles':{'v11':old,'v12-source':source,'v12-narrow':narrow},'unchanged_source_hashes':hashes,'capacity_patch_hashes':capacity,'invalid_cli':invalid}
    if a.smoke_narrow:
        r=subprocess.run([sys.executable,str(ROOT/'play.py'),'--think','--profile','v12-narrow','--depth','3'],capture_output=True,text=True,check=True,timeout=30)
        result=json.loads(r.stdout);assert result['search_profile']['forced_scheme']=='narrow'
        report['separate_initial_position_cli_smoke']=result
    out=ROOT/'test-results/v12-profile-base-proof.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'profiles':list(report['profiles']),'each_addresses_compared':4096,'all_words_equal':True,'cpu_bridge_listing_unchanged':True,'invalid_cli_cases':len(invalid),'proof':str(out),'narrow_smoke':report.get('separate_initial_position_cli_smoke')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
