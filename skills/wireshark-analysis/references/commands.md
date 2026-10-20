# tshark command reference

Contents: reading a capture · display filters · extracting fields · following streams ·
statistics · capture options · exporting objects · output formats · one-liners

The pipes (`sort`, `uniq`, `awk`, `head`) need Git Bash; see "Know the shell" in `SKILL.md`.
`frame.time` contains spaces, so when a pipe splits on whitespace use `frame.time_epoch` or
`frame.time_relative` instead.

## Reading a capture

```bash
tshark -r file.pcapng                  # one summary line per packet
tshark -r file.pcapng -c 50            # first 50 packets
tshark -r file.pcapng -V -c 5          # full dissection of the first 5 packets
tshark -r file.pcapng -V -Y "frame.number==214"   # full dissection of one packet
capinfos file.pcapng                   # duration, packet count, time range
```

## Display filters (`-Y`)

```bash
# protocol
tshark -r file.pcapng -Y "http"
tshark -r file.pcapng -Y "tls"
tshark -r file.pcapng -Y "dns"

# address and port
tshark -r file.pcapng -Y "ip.addr == 192.168.1.1"
tshark -r file.pcapng -Y "ip.src == 10.0.0.1 && ip.dst == 10.0.0.2"
tshark -r file.pcapng -Y "tcp.port == 443"

# TCP flags and problems
tshark -r file.pcapng -Y "tcp.flags.syn == 1 && tcp.flags.ack == 0"   # connection attempts
tshark -r file.pcapng -Y "tcp.flags.reset == 1"
tshark -r file.pcapng -Y "tcp.analysis.retransmission"
tshark -r file.pcapng -Y "tcp.analysis.zero_window"
tshark -r file.pcapng -Y "tcp.analysis.flags"                          # every TCP expert flag

# content
tshark -r file.pcapng -Y 'frame contains "ORA-"'
tshark -r file.pcapng -Y 'http.request.uri contains "/policies"'
tshark -r file.pcapng -Y "http.response.code >= 500"
tshark -r file.pcapng -Y "dns.flags.rcode != 0"

# time window (local time of the capture)
tshark -r file.pcapng -Y 'frame.time >= "2026-10-01 10:15:00" && frame.time <= "2026-10-01 10:16:00"'
```

`contains` is case-sensitive; `matches` takes a case-insensitive regex with `(?i)`:
`http.request.uri matches "(?i)/policies/[0-9]+"`.

## Extracting fields (`-T fields -e`)

```bash
tshark -r file.pcapng -T fields -e ip.src -e ip.dst
tshark -r file.pcapng -Y "http.request" -T fields \
  -e frame.time -e ip.src -e http.host -e http.request.method -e http.request.uri -E header=y
tshark -r file.pcapng -Y "tcp.flags.syn==1 && tcp.flags.ack==0" -T fields \
  -e frame.time -e ip.src -e ip.dst -e tcp.dstport

# CSV
tshark -r file.pcapng -T fields -E separator=, -E quote=d -E header=y \
  -e frame.time -e ip.src -e ip.dst -e tcp.dstport > packets.csv
```

To find a field name, dissect one packet with `-V` or look it up in the
[display filter reference](https://www.wireshark.org/docs/dfref/).

## Following streams

```bash
tshark -r file.pcapng -q -z follow,tcp,ascii,0     # TCP stream 0 as text
tshark -r file.pcapng -q -z follow,tcp,hex,0
tshark -r file.pcapng -q -z follow,udp,ascii,0
tshark -r file.pcapng -q -z follow,http,ascii,0
tshark -r file.pcapng -o tls.keylog_file:keys.log -q -z follow,tls,ascii,0   # decrypted TLS

# which streams involve a host
tshark -r file.pcapng -Y "ip.addr == 192.168.1.1 && tcp" -T fields -e tcp.stream | sort -un
```

## Statistics (`-q -z`)

```bash
tshark -r file.pcapng -q -z io,phs              # protocol hierarchy
tshark -r file.pcapng -q -z conv,tcp            # TCP conversations (also conv,udp / conv,ip / conv,eth)
tshark -r file.pcapng -q -z endpoints,ip        # endpoints (also endpoints,tcp / endpoints,udp)
tshark -r file.pcapng -q -z io,stat,1           # packets and bytes per 1-second bucket
tshark -r file.pcapng -q -z io,stat,1,"tcp.flags.reset==1"   # resets per second
tshark -r file.pcapng -q -z http,tree           # HTTP request/response counts
tshark -r file.pcapng -q -z http_srv,tree       # HTTP requests per server
tshark -r file.pcapng -q -z dns,tree
tshark -r file.pcapng -q -z expert              # errors, warnings, notes
```

A statistic can take a filter as its last part: `-z conv,tcp,"ip.addr==10.20.1.5"`.

## Capture options

```bash
tshark -D                                              # list interfaces (pick by number on Windows)
tshark -i 1 -w capture.pcapng                          # until Ctrl+C
tshark -i 1 -f "host 10.20.1.5 and port 8443" -w c.pcapng   # BPF capture filter
tshark -i 1 -c 500 -w capture.pcapng                   # stop after 500 packets
tshark -i 1 -a duration:60 -w capture.pcapng           # stop after 60 s
tshark -i 1 -b filesize:102400 -b files:10 -w ring.pcapng   # ring buffer, 10 × 100 MB
tshark -i 1 -b duration:3600 -b files:24 -w hourly.pcapng   # one file per hour, keep a day
tshark -i 1 -s 128 -w headers.pcapng                   # headers only (payload cut off)
```

BPF capture filter primitives: `host <ip>`, `net <cidr>`, `port <n>`, `portrange 8000-8100`,
`tcp`, `udp`, `icmp`, `src`/`dst`, combined with `and`, `or`, `not` and parentheses.

## Exporting objects

```bash
tshark -r file.pcapng -q --export-objects http,C:/temp/http-objects
tshark -r file.pcapng -q --export-objects smb,C:/temp/smb-objects
tshark -r file.pcapng -q --export-objects imf,C:/temp/email-objects
```

Only plaintext (or decrypted) transfers can be exported.

## Output formats

| Flag | Format | Use |
|---|---|---|
| `-T text` | summary lines (default) | quick overview |
| `-T fields -e …` | tab-separated fields | scripting, grep, awk |
| `-T json` | full dissection as JSON (`-e` limits the fields) | programmatic parsing |
| `-T ek` | newline-delimited JSON for Elasticsearch bulk import | loading into Elastic / Kibana |
| `-T pdml` | XML | tool integration |
| `-T tabs` | summary lines, tab-delimited | spreadsheets |

## One-liners

```bash
# top talkers by packet count
tshark -r file.pcapng -T fields -e ip.src | sort | uniq -c | sort -rn | head -20

# every distinct destination
tshark -r file.pcapng -T fields -e ip.dst | sort -u

# server names of every TLS connection (SNI)
tshark -r file.pcapng -Y "tls.handshake.type == 1" -T fields -e ip.dst -e tls.handshake.extensions_server_name | sort -u

# largest frames
tshark -r file.pcapng -T fields -e frame.number -e ip.src -e ip.dst -e frame.len | sort -k4 -rn | head

# streams with retransmissions
tshark -r file.pcapng -Y "tcp.analysis.retransmission" -T fields -e tcp.stream | sort -n | uniq -c

# HTTP status code summary
tshark -r file.pcapng -Y "http.response" -T fields -e http.response.code | sort | uniq -c
```
