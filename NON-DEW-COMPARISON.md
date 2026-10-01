# The same labs without DEW

What each experiment looks like done "normally" — by hand over `ssh`, with a stopwatch where timing
matters — next to the DEW version. This is the honest comparison behind "how well did DEW help?"

**Key point up front:** the non-DEW version is a *manual procedure across several terminals*, not a
single script. If you were to collapse it into one bash script with `&`/`sleep`/backgrounded `ssh`,
you'd essentially be re-implementing DEW's scheduling by hand — so the fair "normal" baseline is the
manual, multi-terminal procedure below.

---

## synflood (timed) — DEW wins on effort

**DEW:** one scenario file (`synflood-run-nocookie.json`) + `./dewctl run`. Walk away. The 30/120/30
timing and the stop of every component happen automatically; the cookies-on run is the same file with
two values changed.

**Non-DEW:** 4 terminals + a stopwatch:

```bash
# T1 server:  sudo sysctl -w net.ipv4.tcp_syncookies=0; sudo sysctl -w net.ipv4.tcp_max_syn_backlog=10000
# T2 client:  ip route get 5.6.7.8        # find iface (eth1)
#             sudo tcpdump -nn -i eth1 -w /tmp/nocookie.pcap ip        # leave running
# T3 client:  while true; do curl -s -o /dev/null --max-time 5 http://server; sleep 1; done   # START STOPWATCH
# T4 attacker: (wait until 0:30)  sudo flooder --dst 5.6.7.8 --src 1.1.2.0 --srcmask 255.255.255.0 \
#                                   --dportmin 80 --dportmax 80 --highrate 1000 --proto 6
#  at 2:30 -> Ctrl-C the flooder (T4)
#  at 3:00 -> Ctrl-C the curl loop (T3)
#  then    -> Ctrl-C the tcpdump (T2)
#  ... then repeat ALL of it for cookies on.
```

Roughly comparable in lines, but the manual version is ~7 hand-timed actions across 4 terminals, ×2
runs — error-prone (a late Ctrl-C skews the data) and not repeatable. DEW's length buys exact timing
and a one-command repeat.

---

## dnsmitm (investigative/interactive) — DEW is net overhead

Most tasks are a single command on a single node, so the non-DEW form is *shorter*:

| Task | DEW | Non-DEW |
|---|---|---|
| Part 1 dig | ~7-line scenario + run + view | `ssh client 'dig www.google.com A'` |
| Part 2 gather | ~14-line scenario | `for n in ...; do ssh $n 'ip -br link; ip -br addr'; done` |
| Part 5 config steps | one scenario each | `ssh <node> '<cmd>'` each |

DEW only pulls ahead on the **coordinated before/after** pieces (ARP baseline vs poisoned; DNS spoof
with/without DNSSEC), where it starts a sniffer + runs a trigger + snapshots state together — which
by hand means backgrounded `ssh` + `sleep`. Overall for this lab, plain `ssh` is less to write.

---

## bgphijack (converge-then-observe) — DEW wins on the waits

**DEW:** `bgp-part2.json` — asn4 hijacks, DEW `wait 150` covers BGP convergence, then client + asn3
observe, all in one file.

**Non-DEW:** manual, with real-clock waits:

```bash
# T1 asn4:  telnet localhost bgpd  (interactive: enable / config terminal / router bgp 65004 /
#                                    network 10.1.1.0/24 / end)
#           sudo ip route add 10.1.1.0/24 dev eth2
#           sudo iptables -t nat -A PREROUTING -d 10.1.1.2 ... ; ... POSTROUTING ...
#  --- now WAIT ~5 minutes by the clock for BGP to converge ---
# T2 client:  traceroute -n 10.1.1.2 ; curl ftp://anonymous:x@10.1.1.2/README
# T3 asn3:    sudo vtysh -c "show ip bgp"
```

Comparable lines, but you're babysitting a 5-minute wall-clock wait and an interactive `telnet`
session per step, ×3 parts. DEW's `wait` + `vtysh -c` scripting make it hands-off and repeatable —
the clearest payoff of the three labs.

---

## Bottom line

DEW's per-task footprint is small (~240 lines total, ~16 distinct scenarios). It does **not** reduce
line count on single-node work, but it replaces manual, multi-terminal, stopwatch-timed coordination
with one repeatable file — so it pays off exactly where the experiment's difficulty is *timing and
coordination* (synflood, bgphijack) and costs more than it saves where the work is plain per-node
commands (dnsmitm).
