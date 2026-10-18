from pathlib import Path
import os, platform, subprocess
ROOT=Path(__file__).resolve().parents[1]
SOURCES=['m20_cpu','m20_drum','m20_sys','scp','sim_console','sim_fio','sim_timer','sim_sock','sim_tmxr','sim_ether','sim_tape']
def build():
    extension='dylib' if platform.system()=='Darwin' else 'so'
    output=ROOT/f'engine/libitef-{platform.system().lower()}-{platform.machine()}.{extension}'
    files=[ROOT/'engine/bridge.c',*[ROOT/f'm20/simh/{s}.c' for s in SOURCES]]
    dependencies=files+list((ROOT/'m20/simh').glob('*.h'))+list((ROOT/'engine').glob('*.h'))+[Path(__file__)]
    if output.exists() and output.stat().st_mtime>=max(p.stat().st_mtime for p in dependencies):return output
    temporary=output.with_suffix(output.suffix+'.tmp')
    cmd=[os.environ.get('CC','cc'),'-std=c99','-U__STRICT_ANSI__','-O2','-shared','-fPIC','-D_GNU_SOURCE','-DUSE_INT64','-Im20/simh',*[str(p) for p in files],'-o',str(temporary),'-lm']
    if platform.system()=='Linux':cmd+=['-lrt']
    try:result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
    except FileNotFoundError as e:raise RuntimeError('Не найден компилятор C (cc). Инструкция по установке — в README.md.') from e
    if result.returncode:raise RuntimeError('Не удалось собрать эмулятор. Нужен компилятор C.\n'+result.stderr)
    temporary.replace(output)
    return output
if __name__=='__main__':print(build())
