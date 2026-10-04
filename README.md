# DEW on SPHERE — Education Lab Scenarios

DEW ("Distributed Experiment Workflow") scenarios used to drive three SPHERE classroom lab
exercises end-to-end. Each lab's **setup and tasks were orchestrated through DEW** instead of being
run by hand, as a test of how well DEW fits different kinds of experiments.

DEW is a lightweight per-node agent + a JSON scenario language: a broker (RabbitMQ on one node)
fans out a scenario to per-node agents, which run the commands addressed to them, coordinated by
events (`emit` / `when` / `wait` / `startemit`). Code: `gitlab.com/glawler/dew` (branch
`tuetrung-test`).

A scenario looks like:

```json
{
  "Scenario":   { "task1": "server set_cookies_off emit ready",
                  "task2": "when ready client capture startemit capturing" },
  "Bindings":   { "set_cookies_off": "bash -c \"sudo sysctl -w net.ipv4.tcp_syncookies=0\"",
                  "capture":         "bash -c \"sudo timeout 185 tcpdump ...\"" },
  "Constraints": {}
}
```
Run with `./dewctl run scenario.json` (after `./deploy-dew.sh <nodes> --broker <node>`).

---

## Combined scenarios (`*-full.json`) — current approach

Each lab now has a single **`<lab>-full.json`** that reworks it per three pieces of feedback:

1. **No `bash install`** — each node's install is decomposed into the individual actions it performs
   (copy sources → install packages → copy configs → start/verify service), so the scenario shows the
   real steps instead of shelling out to the lab's `install` script.
2. **Checked emits** — every `emit` is gated on a real success criterion (service active, port
   listening, package present, route in the table), so an event only fires if its step actually
   worked; a failure leaves everything downstream blocked.
3. **One scenario per lab** — setup and tasks chained together in one file.

| File | Status |
|---|---|
| `bgphijack/bgphijack-full.json` | **verified on hardware** — 37 tasks, 0 failures |
| `dnsmitm/dnsmitm-full.json` | **verified on hardware** — 13 tasks, 0 failures (needs the control-net broker, below) |
| `synflood/synflood-full.json` | decomposed install + the proven timed run — pending a validation run |

The per-part files below are the earlier approach, kept for reference until the combined versions are
all hardware-validated.

**Broker note (dnsmitm, bgphijack):** these labs manipulate the experiment network — dnsmitm
rewrites DNS, bgphijack leaves the experiment net unrouted until BGP is up — so DEW's broker must be
reached over the **control net** (172.30.x), not by experiment-net name. Before deploying, add the
broker's control IP to `/etc/hosts` on every node, e.g. for dnsmitm:
`sudo sed -i '1i <cache-control-ip> cache' /etc/hosts`, then `./deploy-dew.sh … --broker cache`.
synflood is a flat routed LAN and needs no such step.

---

## Layout

```
synflood/    TCP SYN flood attack/defense (timed)
dnsmitm/     DNS + ARP man-in-the-middle, then DNSSEC
bgphijack/   BGP prefix + subprefix hijacking
NON-DEW-COMPARISON.md   what the same labs look like without DEW
```

---

## synflood — timed attack/defense

A stopwatch experiment: legitimate web traffic, a SYN flood 30 s later for 120 s, a tcpdump capture,
then connection-duration analysis — run once with SYN cookies off and once on.

| File | What it does |
|---|---|
| `synflood-install.json` | runs each node's install script via DEW (builds the flooder, apache, net-tools) |
| `synflood-run-nocookie.json` | the full timed run with `tcp_syncookies=0` |
| `synflood-run-cookie.json` | same run with `tcp_syncookies=1` (one scenario, two values changed) |
| `synflood-analyze.py` | reads the pcaps, computes per-connection durations (helper, not a scenario) |

**Result:** cookies off → 19 of 80 legit connections starved; cookies on → 0 starved. The whole
30/120/30 stopwatch ran as one DEW scenario, timed precisely and repeated trivially. **Best-case DEW
fit.**

---

## dnsmitm — DNS/ARP MITM, then DNSSEC

Five parts: observe DNS, map the topology, ARP-spoof with ettercap, DNS-spoof with bettercap, then
deploy DNSSEC and show it defeats the spoof.

| File | Part |
|---|---|
| `dnsmitm-setup.json`, `dnsmitm-fix.json` | run the lab install scripts + patch their gaps (missing `dnsutils`, broken build-deps) |
| `dns-part1.json`, `dns-part1b.json` | Part 1 — `dig` the exercise DNS tree |
| `dns-part2-gather.json`, `dns-part2-baseline.json` | Part 2 — MAC/IP of all nodes; baseline (no MITM) |
| `dns-part3-mitm.json` | Part 3 — ettercap ARP spoof (headless `-T`) + capture + trigger |
| `dns-part4-pull.json`, `dns-part4-spoof2.json` | Part 4 — bettercap DNS spoof (docker, headless `-eval`) → client gets the attacker's IP |
| `dns-fix-resolv.json` | stop the client escaping to the real DNS resolver |
| `dns-part5-sign.json`, `dns-part5-cache.json`, `dns-part5-client.json`, `dns-part5-attack.json` | Part 5 — sign the zone, add trust anchor, verify `ad` bit, replay attack → `SERVFAIL` |
| `sign-google.sh` | DNSSEC zone-signing script run on auth (helper) |

(`dns-part4-spoof.json`, `dns-part5-dig.json` are an early/refined variant and a tooling fix.)

**Result:** bettercap (headless, via DEW) landed the spoof; DNSSEC then rejected the identical
attack. **Weaker DEW fit** — most steps are one-off single-node commands where DEW adds overhead; it
helped on the coordinated before/after demos.

---

## bgphijack — BGP prefix/subprefix hijack

Seven-node AS topology (asn1–asn4, server, client, attacker) running FRR. Observe normal routing,
then hijack the ftp server's prefix, then its subprefix.

| File | What it does |
|---|---|
| `bgp-setup.json` | run each node's FRR install/config via DEW (routes the experiment net) |
| `bgp-part1.json`, `bgp-part1b.json` | Part 1 — baseline path + ftp README + AS path |
| `bgp-part2.json` + `hijack-prefix.sh` | Part 2 — asn4 announces `10.1.1.0/24`; wait for convergence; observe divert |
| `bgp-part3.json` + `hijack-subprefix.sh` | Part 3 — asn4 announces `10.1.1.0/25` (longest-prefix wins) |

**Result:** the hijack diverted the client to the attacker's ftp (forged README); DEW's `wait`
timer covered BGP convergence each time. **Best fit** — "change config → wait for convergence →
observe" is exactly DEW's strength. Also the one lab where DEW's broker had to run on the **control
network** (the experiment net isn't routed until BGP is up).

---

## DEW vs non-DEW — the finding

| Lab | Shape | DEW fit |
|---|---|---|
| synflood | timed parallel attack/defense | **ideal** |
| dnsmitm | investigative / interactive / config, single-node | **weak** (net overhead) |
| bgphijack | config → converge → observe | **best** |

**DEW earns its keep on timing, parallelism, repeatability, and coordinated before/after** — and is
pure overhead for one-shot single-node commands. Scenario size is small: **~240 lines across the
scenario files, ~16 distinct scenarios** (the rest are off/on variants, refined re-runs, and tiny
fixes). See [`NON-DEW-COMPARISON.md`](NON-DEW-COMPARISON.md) for the by-hand equivalents.

**Reach limits found:** DEW can't relay data between nodes (a DNSSEC key had to be `scp`'d
XDC-side); and on an unrouted network it can't bootstrap its broker on the experiment net (bgphijack
used the control net). It also faithfully ran the labs' install scripts, which surfaced their
EOL-image bugs — a feature, not a DEW fault.
