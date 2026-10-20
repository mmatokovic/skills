# Security analysis

Contents: cleartext credentials · port scans · DNS tunnelling and beaconing · ARP spoofing ·
suspicious downloads and exfiltration · incident response · wireless

For authorised work only: your own systems, an agreed investigation, or a capture handed over
for that purpose. Report what is exposed (protocol, host, account name) — do not copy passwords,
hashes or tokens into the conversation, a ticket or a file nobody asked for.

## Cleartext credentials

The question is usually "does anything still send credentials in clear text":

```bash
# protocols that carry credentials without TLS
tshark -r file.pcapng -Y "(http.authorization or ftp.request.command == \"PASS\" or pop.request.command == \"PASS\" or imap.request contains \"LOGIN\" or smtp.req.command == \"AUTH\") and not tls" \
  -T fields -e ip.src -e ip.dst -e _ws.col.Protocol | sort | uniq -c

# HTTP Basic auth — tshark decodes it already, no base64 step needed
tshark -r file.pcapng -Y "http.authbasic" -T fields -e ip.src -e http.host -e http.authbasic

# login forms posted over plain HTTP
tshark -r file.pcapng -Y 'http.request.method == "POST" and http.file_data matches "(?i)pass(word|wd)?="' \
  -T fields -e ip.src -e http.host -e http.request.uri

# FTP accounts
tshark -r file.pcapng -Y 'ftp.request.command == "USER"' -T fields -e ip.src -e ftp.request.arg

# NTLM and Kerberos account names (identities, not secrets)
tshark -r file.pcapng -Y "ntlmssp.auth.username" -T fields -e ip.src -e ntlmssp.auth.domain -e ntlmssp.auth.username
tshark -r file.pcapng -Y "kerberos.CNameString" -T fields -e ip.src -e kerberos.CNameString -e kerberos.realm
```

## Port scans

```bash
# many SYNs from one source to many ports
tshark -r file.pcapng -Y "tcp.flags.syn == 1 && tcp.flags.ack == 0" -T fields -e ip.src -e tcp.dstport \
  | sort -u | cut -f1 | uniq -c | sort -rn | head
```

A source that touches hundreds of ports, most of them answered with RST, is a scan.

## DNS tunnelling and beaconing

```bash
# unusually long query names
tshark -r file.pcapng -Y "dns.flags.response == 0" -T fields -e dns.qry.name | awk 'length > 50' | sort | uniq -c

# registered domains with many distinct subdomains (DGA, tunnelling)
tshark -r file.pcapng -Y "dns.flags.response == 0" -T fields -e dns.qry.name \
  | awk -F. '{print $(NF-1)"."$NF}' | sort | uniq -c | sort -rn | head

# beaconing: connections to the same host at regular intervals
tshark -r file.pcapng -Y "tcp.flags.syn==1 && tcp.flags.ack==0" -T fields -e ip.dst -e frame.time_relative \
  | sort -k1,1 -k2,2n | awk '$1==h {printf "%s %.1f\n", $1, $2-t} {h=$1; t=$2}' | sort | uniq -c | sort -rn | head
```

The last command prints the gap between successive connections per host; the same host with
the same gap many times over is a beacon (or a health check — check what the host is).

## ARP spoofing

```bash
tshark -r file.pcapng -Y "arp.duplicate-address-detected or arp.duplicate-address-frame" \
  -T fields -e frame.number -e arp.src.proto_ipv4 -e arp.src.hw_mac
tshark -r file.pcapng -q -z conv,eth,arp
```

## Suspicious downloads and exfiltration

```bash
# executables over HTTP
tshark -r file.pcapng -Y 'http.content_type contains "application/x-msdownload" or http.content_type contains "application/x-dosexec" or http.content_type contains "application/octet-stream"' \
  -T fields -e ip.src -e http.response_for.uri -e http.content_type

# large uploads
tshark -r file.pcapng -Y "http.request.method == POST && http.content_length > 1000000" \
  -T fields -e ip.src -e http.host -e http.content_length

# the hosts receiving the most bytes
tshark -r file.pcapng -q -z conv,ip
```

## Incident response

```bash
# capture during the incident (Windows: interface number from tshark -D)
tshark -i 1 -a duration:300 -w C:/temp/incident.pcapng

# lateral movement candidates
tshark -r incident.pcapng -Y "smb2 or rdp or ssh or kerberos" -T fields -e ip.src -e ip.dst -e _ws.col.Protocol | sort | uniq -c

# indicators: every external IP and every queried domain
tshark -r incident.pcapng -T fields -e ip.dst | sort -u > ioc_ips.txt
tshark -r incident.pcapng -Y "dns.qry.name" -T fields -e dns.qry.name | sort -u > ioc_domains.txt

# carve transferred files for analysis in a sandbox
tshark -r incident.pcapng -q --export-objects http,C:/temp/artifacts
```

## Wireless

Needs an adapter in monitor mode, which Npcap on Windows supports only for some adapters.

```bash
tshark -r wifi.pcapng -Y "wlan.fc.type_subtype == 0x08" -T fields -e wlan.ssid -e wlan.bssid | sort -u   # beacons
tshark -r wifi.pcapng -Y "wlan.fc.type_subtype == 0x0c" -T fields -e wlan.sa -e wlan.da                  # deauthentication
tshark -r wifi.pcapng -Y "wlan.fc.type_subtype == 0x04" -T fields -e wlan.sa -e wlan.ssid                # probe requests
tshark -r wifi.pcapng -Y "eapol"                                                                          # WPA handshakes
```
