import subprocess,re
R='.'
h=[(i+1,l.strip()) for i,l in enumerate(open(R+'/docs/decisions.md',encoding='utf-8')) if re.match(r'#+ ',l) and 'runtime-registry' in l]
for x in h: print(x)
print(len(h),'entries;',sum('exempt' in l for _,l in h),'name the exemption')
o=subprocess.run(['git','-C',R,'log','--format=%h %ad %s','--date=format-local:%m-%d %H:%M:%S','--since=2026-11-06T12:40','--until=2026-11-06T13:38'],capture_output=True,text=True).stdout.splitlines()
c=[l for l in o if 'runtime-registry' in l]
print(len(c),'commits naming runtime-registry 12:43-13:37');print('\n'.join(c))
