#!/usr/bin/env python3
import subprocess, sys, os, re, statistics
CLIENT, SERVER, PORT, CAP = "1.1.2.3", "5.6.7.8", "80", 200.0
pat = re.compile(r"^(\d+\.\d+) IP (\d+\.\d+\.\d+\.\d+)\.(\d+) > (\d+\.\d+\.\d+\.\d+)\.(\d+): Flags \[([^\]]*)\]")
def analyze(pcap):
    bpf = "tcp and host %s and host %s and port %s" % (CLIENT, SERVER, PORT)
    txt = subprocess.run(["tcpdump","-nn","-tt","-r",pcap,bpf], capture_output=True, text=True).stdout
    conns = {}
    for ln in txt.splitlines():
        m = pat.match(ln)
        if not m: continue
        t = float(m.group(1)); sip,sp,dip,dp,fl = m.group(2),m.group(3),m.group(4),m.group(5),m.group(6)
        if sip==CLIENT and dip==SERVER and dp==PORT: cp, from_c = sp, True
        elif sip==SERVER and sp==PORT and dip==CLIENT: cp, from_c = dp, False
        else: continue
        c = conns.setdefault(cp, {"start":None,"end":None,"fin":False,"closed":False})
        if from_c and fl=="S" and c["start"] is None: c["start"]=t          # client SYN = start
        if "F" in fl: c["fin"]=True; c["end"]=t
        if c["fin"] and fl=="." and not c["closed"]: c["end"]=t; c["closed"]=True
        if "R" in fl and not c["closed"]: c["end"]=t; c["closed"]=True
    durs, rows = [], []
    for cp,c in conns.items():
        if c["start"] is None: continue                                     # skip flood-spoofed fakes
        d = (c["end"]-c["start"]) if (c["end"] is not None and (c["closed"] or c["fin"])) else CAP
        if d < 0: d = CAP
        durs.append(d); rows.append((c["start"], d))
    rows.sort(); t0 = rows[0][0] if rows else 0
    capped = sum(1 for d in durs if d >= CAP)
    ok = [d for d in durs if d < CAP]
    name = os.path.basename(pcap)
    print("=== %s ===" % name)
    print("  client legit connections: %d" % len(durs))
    print("  completed (closed):       %d" % len(ok))
    print("  starved (== %.0fs cap):     %d" % (CAP, capped))
    if ok: print("  completed dur min/med/max: %.3f / %.3f / %.3f s" % (min(ok), statistics.median(ok), max(ok)))
    csv = "/tmp/%s.durations.csv" % name
    with open(csv,"w") as f:
        f.write("start_offset_s,duration_s\n")
        for st,d in rows: f.write("%.3f,%.3f\n" % (st-t0, d))
    print("  csv -> %s" % csv)
for p in sys.argv[1:]: analyze(p)
