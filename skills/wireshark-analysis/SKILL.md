---
name: wireshark-analysis
description: >-
  Analyse network packet captures and run live captures with tshark (Wireshark CLI) from the terminal. Use when the user has a .pcap/.pcapng or wants to capture traffic, and when an integration call misbehaves on the wire — Integration Server, API Gateway or a Spring service calling a backend or partner that hangs, times out, gets "Connection reset", fails the TLS handshake, or returns errors — or when a request has to be found in a capture by a flow or correlation ID (X-IL-flowID, X-Correlation-Id). Also covers display and capture filters, following TCP/TLS streams, statistics, exporting objects, and authorised security analysis (port scans, cleartext credentials, DNS tunnelling, C2 beaconing). Trigger phrases: "analyze this pcap", "capture packets", "tshark filter", "follow the TCP stream", "why does the connection reset", "TLS handshake fails", "find the request in the capture".
---

# Network Traffic Analysis with tshark

Read captures and capture traffic with **tshark**, the command-line engine of Wireshark. Most
requests in this team are not security forensics but **integration debugging**: a call from
Integration Server, API Gateway or a Spring service to a backend or partner hangs, resets, fails
TLS, or returns the wrong thing, and the capture is the only place that shows what really
happened on the wire. Start there; the security material is in a reference file.

Captures hold credentials, tokens and personal data. Capture only traffic you are authorised to
capture, quote frame numbers and headers rather than pasting payloads, and say where the file
should be deleted from when the analysis is done.

## Before the first command

**Find tshark.** On the team's Windows machines and servers it is usually *not* on PATH. Check in
this order and use whichever works, quoting the full path:

```powershell
tshark --version
& "C:\Program Files\Wireshark\tshark.exe" --version
```

In Git Bash the same file is `"/c/Program Files/Wireshark/tshark.exe"`. If neither exists,
Wireshark is not installed — see the plugin README. `capinfos.exe` and `dumpcap.exe` sit in the
same folder.

**Know the shell.** The examples below use bash pipes (`sort`, `uniq`, `awk`), which work in Git
Bash but not in PowerShell. In PowerShell use `Sort-Object`, `Group-Object` and
`Select-String`, or write the fields to a file first.

**Ask for the context, or read it from the capture.** A capture is only readable against the
question it was taken for. Establish:

- where it was taken (on the IS host, on the backend, on a gateway) — that decides whose view of
  the conversation you are seeing;
- the client and server IP:port of the call that failed, and the time it failed (from the IS
  server log or the user);
- whether the call is HTTPS — if it is, URLs, headers and bodies are encrypted in the capture.

## Workflow

### 1. Overview

```bash
capinfos file.pcapng                     # duration, packet count, first and last packet time
tshark -r file.pcapng -q -z conv,tcp     # who talked to whom, bytes, duration
tshark -r file.pcapng -q -z expert       # resets, retransmissions, zero windows, malformed packets
```

### 2. Isolate the conversation

Everything after this is about one TCP connection, identified by `tcp.stream`:

```bash
# connections opened to the backend, and when
tshark -r file.pcapng -Y "ip.addr==10.20.1.5 && tcp.port==8443 && tcp.flags.syn==1 && tcp.flags.ack==0" \
  -T fields -e tcp.stream -e frame.time -e ip.src -e tcp.srcport

# one conversation, packet by packet, with the gap since the previous packet of that stream
tshark -r file.pcapng -Y "tcp.stream==7" -o tcp.calculate_timestamps:TRUE \
  -T fields -e frame.number -e tcp.time_delta -e ip.src -e _ws.col.Info
```

`tcp.time_delta` is what shows a hang: a 60-second gap before a RST or FIN is the client's
timeout, and the side that sent the last data packet before the gap is the side that was waiting.

### 3. Diagnose by what the stream shows

| What you see | What it means | Next check |
|---|---|---|
| SYN, SYN, SYN… no SYN-ACK | nothing answers: firewall drop, wrong IP/port, routing | the same SYN from another host; the firewall rule |
| SYN → immediate RST, ACK | host reachable, port closed | is the service listening on that port |
| Client Hello → fatal Alert from the server (Handshake Failure, Protocol Version) | the server rejected the offer before sending its certificate: no common TLS version or cipher suite, or a missing/unknown SNI | compare `tls.handshake.version`, `tls.handshake.ciphersuite`, `tls.handshake.extensions_server_name` in the Client Hello with what the server accepts |
| Server Hello + Certificate → Alert from the **client** (Unknown CA, Bad Certificate, Certificate Unknown) | the client does not trust the server certificate | the IS / JVM truststore; the chain the server sends (`tls.handshake.certificate`) |
| Server sends Certificate Request, client answers with an empty Certificate, then Alert | mutual TLS: the client had no client certificate to offer | the IS keystore and the alias configured for that endpoint |
| Handshake completes, request sent, then silence until RST/FIN | the backend did not answer within the client timeout | the backend at that time; the length of the gap |
| Data flows, then a RST after an idle period, and the next request on that connection fails | a load balancer or firewall idle timeout killed a pooled connection | time since the previous packet on that stream vs. the idle timeout; pool keep-alive settings |
| `tcp.analysis.retransmission`, `tcp.analysis.zero_window` | packet loss, or a receiver that cannot keep up | `-q -z expert`; which side's window reaches zero |
| A full HTTP response with 4xx/5xx | the network is fine; the problem is in the application | status line and response body (plaintext only) |

Report the finding with frame numbers and timestamps ("frame 214: the request goes out at 10:15:02.118,
and nothing comes back until the client sends RST at 10:16:02.120"), not only a conclusion.

### 4. Encrypted traffic (HTTPS)

Over TLS the capture shows IPs, ports, timings, the SNI and the handshake — **not** the URL,
headers or body. A filter such as `http contains "flow-id"` then silently matches nothing. Say so
before giving such a filter, and use one of these instead:

- **Correlate without decrypting.** Find the stream by IP:port and time (from the IS log) or by
  SNI, then read the timings and the handshake. That answers most "hangs / resets / TLS fails"
  questions on its own.
- **Capture where it is plaintext.** A call that is HTTPS to the backend may be plain HTTP on an
  earlier hop, e.g. client → API Gateway inside the network.
- **Decrypt with a key log.** tshark reads an NSS key log with `-o tls.keylog_file:C:\temp\keys.log`.
  Browsers and curl write one when `SSLKEYLOGFILE` is set; a **JVM (IS, Spring) does not** — it
  needs a Java agent such as jSSLKeyLog, which means a restart with an extra `-javaagent` on a
  shared server, so agree it with the server owner first. An RSA private key only decrypts
  non-(EC)DHE cipher suites, which modern servers rarely negotiate.

### 5. Find a request by flow or correlation ID (plaintext only)

```bash
# which stream carries it
tshark -r file.pcapng -Y 'http.request.line contains "7f3a9c21-55e0-4b1e-9d0a-2c41e8f0b6aa"' \
  -T fields -e tcp.stream -e frame.number -e frame.time -e http.request.method -e http.request.uri

# request and response of that stream side by side
tshark -r file.pcapng -Y "http && tcp.stream==12" -T fields -e frame.number -e frame.time \
  -e http.request.method -e http.request.uri -e http.response.code -e http.time -E header=y

# the full exchange as text
tshark -r file.pcapng -q -z follow,tcp,ascii,12
```

`http.request.line` matches request header lines; use `http contains "…"` when the ID may also be
in a response header or body. `http.time` is the server's response time for that request. With a
key log, add `-o tls.keylog_file:…` to every command and follow with `follow,tls,ascii,N`.

## Live capture

On Windows, capturing needs **Npcap** (installed with Wireshark) and a shell started **as
Administrator**. Interfaces have no Linux names such as `eth0`; list them and pick by number:

```powershell
& "C:\Program Files\Wireshark\tshark.exe" -D
# 1. \Device\NPF_{4B1F...} (Ethernet0)
# 2. \Device\NPF_Loopback (Adapter for loopback traffic capture)
```

For anything longer than a few minutes — waiting for an intermittent error — use a **capture
filter** so only the relevant traffic is written, and a **ring buffer** so the disk cannot fill:

```powershell
& "C:\Program Files\Wireshark\tshark.exe" -i 1 -f "host 10.20.3.40 and port 1521" `
  -b filesize:102400 -b files:20 -w C:\temp\is-db.pcapng
```

- `-f` is a BPF capture filter (`host`, `net`, `port`, `tcp`, `and`/`or`/`not`), applied while
  capturing. `-Y` is a display filter and does not reduce what is written to disk.
- `-b filesize:102400 -b files:20` keeps the newest 20 files of 100 MB each. `-a duration:3600`
  stops after an hour instead.
- For multi-hour captures `dumpcap.exe` (same arguments) uses far less memory than tshark.
- Do not cut packets short with `-s` when the HTTP body or the TNS payload is needed.
- Ask for the exact time of the next failure from the IS log; that is how the right file and
  stream are found afterwards.
- Traffic to `localhost` is on the loopback adapter, not the Ethernet one.

## Reference files

| Read when… | File |
|---|---|
| Building a filter, extracting fields, statistics, following streams, exporting objects, output formats | `references/commands.md` |
| Protocol-specific analysis: HTTP, TLS, DNS, Oracle TNS, SMB | `references/protocols.md` |
| Authorised security work: cleartext credentials, port scans, DNS tunnelling, C2 beaconing, ARP spoofing, wireless | `references/security.md` |

## Links

- [TShark man page](https://www.wireshark.org/docs/man-pages/tshark.html)
- [Display filter reference](https://www.wireshark.org/docs/dfref/)
- [TLS decryption](https://wiki.wireshark.org/TLS#tls-decryption)
