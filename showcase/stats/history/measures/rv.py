import subprocess,hashlib,re
G='.'
def git(*a): return subprocess.run(['git','-C',G,*a],capture_output=True).stdout
log=git('log','--reverse','--format=%H|%ad|%s','--date=format-local:%m-%d %H:%M','--','engine/tests/data/golden.txt').decode().splitlines()
same=git('show','HEAD:scripts/registry.py').decode()
m=re.search(r'SAME_RULES\s*=\s*\{(.*?)\n\}',same,re.S); print('SAME_RULES', m.group(1)[:600] if m else None)
for l in log:
    h,d,s=l.split('|',2)
    b=git('show',h+':engine/tests/data/golden.txt').replace(b'\r\n',b'\n')
    print(d, hashlib.sha256(b).hexdigest()[:16], len(b.splitlines()), s[:90])
