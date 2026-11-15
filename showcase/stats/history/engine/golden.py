import subprocess, hashlib
R='.'
hs=subprocess.run(['git','-C',R,'log','--reverse','--format=%h|%ad','--date=format:%m-%d %H:%M','--','engine/tests/data/golden.txt'],capture_output=True,text=True).stdout.split()
for l in subprocess.run(['git','-C',R,'log','--reverse','--format=%h|%ad','--date=format:%m-%d_%H:%M','--','engine/tests/data/golden.txt'],capture_output=True,text=True).stdout.split():
    h,d=l.split('|')
    b=subprocess.run(['git','-C',R,'show',h+':engine/tests/data/golden.txt'],capture_output=True).stdout
    print(d,h,hashlib.sha256(b.replace(b'\r\n',b'\n')).hexdigest()[:16],b.count(b'\n'))
