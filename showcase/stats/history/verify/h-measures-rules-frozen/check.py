import subprocess, hashlib
R="."
SAME={"e9c10f64df68a215":"7042d1d6a6149ba0"}
log=subprocess.run(["git","-C",R,"log","--reverse","--format=%h %ad","--date=format-local:%m-%d %H:%M","--","engine/tests/data/golden.txt"],capture_output=True,text=True).stdout.split("\n")
for l in filter(None,log):
    h,dt=l.split(" ",1)
    b=subprocess.run(["git","-C",R,"show",f"{h}:engine/tests/data/golden.txt"],capture_output=True).stdout.replace(b"\r\n",b"\n")
    v=hashlib.sha256(b).hexdigest()[:16]
    lines=b.split(b"\n")
    print(h,dt,v,SAME.get(v,v)[:8],len(lines),len(b), lines[0][:80])
