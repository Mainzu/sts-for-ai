import subprocess, hashlib
R="."
SAME={"e9c10f64df68a215":"7042d1d6a6149ba0"}
log=subprocess.run(["git","-C",R,"log","--reverse","--date=iso-strict","--format=%h %ad %cd","--","engine/tests/data/golden.txt"],capture_output=True,text=True).stdout.split("\n")
for l in log:
    if not l: continue
    h,ad,cd=l.split()
    b=subprocess.run(["git","-C",R,"show",f"{h}:engine/tests/data/golden.txt"],capture_output=True).stdout.replace(b"\r\n",b"\n")
    raw=hashlib.sha256(b).hexdigest()[:16]
    lines=b.split(b"\n"); 
    first=set(x.split()[0] if x.split() else b"" for x in lines)
    print(h,ad,cd,raw,SAME.get(raw,raw),len(lines), len(b))
