# Per-experiment walkthrough: DEW vs non-DEW commands

For each of the three labs: the commands to run it **with DEW**, the commands to run it **by hand**
(no DEW), and a short comparison. "Non-DEW" means the normal way — `ssh node 'cmd'`, `for` loops, and
multiple terminals with a stopwatch where timing matters. (If you collapsed the manual version into a
single bash script with `&`/`sleep`, you'd be re-implementing DEW's scheduling, so the honest baseline
is the manual multi-terminal procedure.)

Assumes the experiment is materialized and the XDC is attached to it. DEW also needs a one-time
`./deploy-dew.sh <nodes> --broker <node>`.

---

## 1. synflood — timed SYN-flood attack/defense

### With DEW
```bash
# one-time: deploy DEW (broker on server)
cd ~/dew/sphere && ./deploy-dew.sh server attacker client --broker server
# setup (run the lab install scripts on every node, in parallel)
for n in attacker client server; do scp -r /share/education/synflood/$n $n:/tmp/; done
./dewctl run ~/synflood-install.json
# the timed experiment — one command, walk away (~3 min). Repeat for cookies on.
./dewctl run ~/synflood-run-nocookie.json
./dewctl run ~/synflood-run-cookie.json
```
The scenario encodes the whole stopwatch (start traffic, +30 s attack, stop at 120 s / 180 s / 185 s)
with `when`/`wait`/`startemit` + `timeout`, so nothing is hand-timed.

### Without DEW (4 terminals + a stopwatch, per cookie setting)
```bash
# T1 server:
sudo sysctl -w net.ipv4.tcp_syncookies=0
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=10000
# T2 client (find iface, start capture, leave running):
ip route get 5.6.7.8                # -> eth1
sudo tcpdump -nn -i eth1 -w /tmp/nocookie.pcap ip
# T3 client (start legit traffic; START STOPWATCH now):
while true; do curl -s -o /dev/null --max-time 5 http://server; sleep 1; done
# T4 attacker (WAIT until 0:30, then):
sudo flooder --dst 5.6.7.8 --src 1.1.2.0 --srcmask 255.255.255.0 --dportmin 80 --dportmax 80 --highrate 1000 --proto 6
#  at 2:30 -> Ctrl-C flooder (T4)
#  at 3:00 -> Ctrl-C curl loop (T3)
#  then    -> Ctrl-C tcpdump (T2)
#  ...then repeat EVERYTHING with tcp_syncookies=1 and a 'cookie.pcap' name.
```

### Comparison
Roughly the same number of lines, but the manual version is ~7 hand-timed actions across 4 terminals,
done **twice** — and a mistimed Ctrl-C corrupts the data. DEW's version is one command you re-run with
one value changed. **DEW clearly wins on effort and repeatability here.**

---

## 2. dnsmitm — DNS/ARP MITM, then DNSSEC

### With DEW
```bash
# deploy (broker on cache)
cd ~/dew/sphere && ./deploy-dew.sh cache attacker auth client --broker cache
# setup + fix lab-script gaps
for n in client cache auth attacker; do scp -r /share/education/dnsmitm/$n $n:/tmp/; done
./dewctl run ~/dnsmitm-setup.json
./dewctl run ~/dnsmitm-fix.json
# tasks
./dewctl run ~/dns-part1.json        # dig
./dewctl run ~/dns-part2-gather.json # MAC/IP of all nodes
./dewctl run ~/dns-part2-baseline.json
./dewctl run ~/dns-part3-mitm.json   # ettercap ARP spoof
./dewctl run ~/dns-part4-spoof2.json # bettercap DNS spoof
# ... part 5 (DNSSEC): sign, cache trust-anchor, client verify, replay attack
```

### Without DEW (mostly one ssh per step)
```bash
# Part 1:
ssh client 'dig www.google.com A'
# Part 2 (gather MAC/IP from every node):
for n in client cache auth attacker; do echo "== $n =="; ssh $n 'ip -br link; ip -br -4 addr'; done
# Part 2 baseline (2 terminals): T1 attacker: sudo tcpdump -nn -i eth1 icmp ;  T2 cache: ping -c5 10.1.2.3
# Part 3 ettercap (2 terminals + trigger): T1 attacker: sudo ettercap -T -i eth1 -M arp:remote /10.1.2.2// /10.1.2.3//
#                                          T2 cache: ping -c5 10.1.2.3 ; then read cache's ARP table
# Part 4 bettercap: attacker: sudo docker run -it --privileged --net=host bettercap/bettercap -iface eth1
#                   (then type the dns.spoof/arp.spoof commands in the UI) ; client: dig www.google.com
# Part 5 DNSSEC: ssh auth '<sign zone>' ; ssh cache '<add trust-anchor, reload>' ; ssh client 'dig +dnssec ...'
```

### Comparison
For the single-node steps (dig, gather, config), plain `ssh` is **shorter** than a JSON scenario +
`dewctl run`. DEW only helps on the coordinated before/after pieces (sniffer + trigger + snapshot
together). **Net: non-DEW is less to write for this lab** — most of it isn't timed or parallel.

---

## 3. bgphijack — BGP prefix/subprefix hijack

### With DEW
```bash
# broker must be on the control net (experiment net isn't routed until BGP is up):
for n in asn1 asn2 asn3 asn4 attacker client server; do ssh $n "grep -q '^172.30.0.11 asn1$' /etc/hosts || sudo sed -i '1i 172.30.0.11 asn1' /etc/hosts"; done
cd ~/dew/sphere && ./deploy-dew.sh asn1 asn2 asn3 asn4 attacker client server --broker asn1
# setup FRR on every node (routes the experiment net)
for n in asn1 asn2 asn3 asn4 attacker client server; do scp -r /share/education/bgphijack/$n $n:/tmp/; done
./dewctl run ~/bgp-setup.json
# tasks (each waits for BGP convergence automatically)
./dewctl run ~/bgp-part1.json        # baseline path
./dewctl run ~/bgp-part2.json        # prefix hijack -> wait 150s -> observe divert
./dewctl run ~/bgp-part3.json        # subprefix hijack
```

### Without DEW (per-node ssh + real-clock waits + interactive telnet)
```bash
# Part 1: remove shadow route, then observe
ssh asn2 'sudo ip route del 10.1.1.0/24'; ssh asn3 'sudo ip route del 10.1.1.0/24'
# --- wait ~30s for convergence ---
ssh client 'traceroute -n 10.1.1.2; curl ftp://anonymous:x@10.1.1.2/README'
ssh asn3 'sudo vtysh -c "show ip bgp"'
# Part 2 hijack: on asn4 (interactive telnet):
#   telnet localhost bgpd  -> enable / config terminal / router bgp 65004 / network 10.1.1.0/24 / end
ssh asn4 'sudo ip route add 10.1.1.0/24 dev eth2; sudo iptables -t nat -A PREROUTING -d 10.1.1.2 ... ; ... POSTROUTING ...'
# --- WAIT ~5 MINUTES by the clock for BGP to converge ---
ssh client 'traceroute -n 10.1.1.2; curl ftp://anonymous:x@10.1.1.2/README'
# Part 3: repeat with 'no network 10.1.1.0/24' + 'network 10.1.1.0/25', another 5-min wait, re-observe.
```

### Comparison
Comparable lines, but you babysit a ~5-minute wall-clock wait and an interactive `telnet` session per
part, ×3. DEW's `wait` timer + `vtysh -c` scripting make each part hands-off and repeatable. **DEW
wins** — this "change config → wait for convergence → observe" shape is its sweet spot. (Also: on this
unrouted topology DEW's broker had to run on the control network — the one lab where that was needed.)

---

## Overall

| Lab | Non-DEW effort | DEW advantage |
|---|---|---|
| synflood | 4 terminals, stopwatch, ×2 | exact timing, one-command repeat |
| dnsmitm | mostly single `ssh` cmds | little — net overhead |
| bgphijack | ssh + 5-min waits + telnet, ×3 | hands-off convergence waits, repeatable |

DEW's value isn't fewer lines — it's replacing **manual timing and multi-node coordination** with one
repeatable file. It pays off where the experiment's difficulty *is* timing/coordination (synflood,
bgphijack) and costs more than it saves on plain per-node commands (dnsmitm).
