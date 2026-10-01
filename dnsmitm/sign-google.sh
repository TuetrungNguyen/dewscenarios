#!/bin/bash
set -e
cd /etc/bind/zones
rm -f Kgoogle.com.*                                   # clean any prior keys (idempotent re-runs)
dnssec-keygen -a RSASHA256 -b 1024 -n ZONE google.com          # ZSK
dnssec-keygen -a RSASHA256 -b 2048 -f KSK -n ZONE google.com   # KSK
dnssec-signzone -S -o google.com -N INCREMENT db.google.com    # smart-sign -> db.google.com.signed
sed -i 's#/etc/bind/zones/db.google.com"#/etc/bind/zones/db.google.com.signed"#' /etc/bind/named.conf.local
rndc reload
echo "=== zone DNSKEYs ==="
dig @localhost google.com DNSKEY +short
echo "=== signed answer check ==="
dig @localhost +dnssec www.google.com A +noall +answer
