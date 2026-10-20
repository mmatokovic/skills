# Protocol analysis

Contents: HTTP · TLS · DNS · Oracle TNS · SMB

## HTTP

Plaintext only — over HTTPS see "Encrypted traffic" in `SKILL.md`.

```bash
# requests
tshark -r file.pcapng -Y "http.request" -T fields -e frame.number -e ip.src -e http.host \
  -e http.request.method -e http.request.uri

# responses with the request they answer and the server time
tshark -r file.pcapng -Y "http.response" -T fields -e frame.number -e http.request_in \
  -e http.response.code -e http.time -e http.content_type

# slow responses (over 5 s)
tshark -r file.pcapng -Y "http.time > 5" -T fields -e tcp.stream -e http.request_in -e http.time

# a header anywhere in the request
tshark -r file.pcapng -Y 'http.request.line contains "X-IL-flowID"' -T fields -e tcp.stream -e http.request.line

# user agents, cookies, bodies
tshark -r file.pcapng -Y "http.user_agent" -T fields -e ip.src -e http.user_agent
tshark -r file.pcapng -Y "http.cookie" -T fields -e ip.src -e http.cookie
tshark -r file.pcapng -Y "http.request.method == POST" -T fields -e http.file_data
```

HTTP on a non-standard port (Integration Server's default is 5555) is dissected only when
tshark recognises the port; otherwise add `-d tcp.port==5555,http`.

## TLS

```bash
# Client Hello: what the client offers
tshark -r file.pcapng -Y "tls.handshake.type == 1" -T fields -e frame.number -e ip.dst \
  -e tls.handshake.extensions_server_name -e tls.handshake.extensions.supported_version \
  -e tls.handshake.ciphersuite

# Server Hello: what was chosen
tshark -r file.pcapng -Y "tls.handshake.type == 2" -T fields -e frame.number -e ip.src \
  -e tls.handshake.version -e tls.handshake.extensions.supported_version -e tls.handshake.ciphersuite

# alerts: who sent them and which one
tshark -r file.pcapng -Y "tls.alert_message" -T fields -e frame.number -e ip.src \
  -e tls.alert_message.level -e tls.alert_message.desc

# certificates the server sent (subject and issuer)
tshark -r file.pcapng -Y "tls.handshake.type == 11" -V | grep -E "rdnSequence|subject|issuer"

# certificate request (mutual TLS) and what the client sent back
tshark -r file.pcapng -Y "tls.handshake.type == 13 || tls.handshake.type == 11" -T fields \
  -e frame.number -e ip.src -e tls.handshake.type -e tls.handshake.certificate_length
```

Alert descriptions that matter most: 40 Handshake Failure (no common parameters), 70 Protocol
Version, 112 Unrecognized Name (SNI), 48 Unknown CA, 42 Bad Certificate, 46 Certificate Unknown,
116 Certificate Required. For TLS 1.3 the legacy `tls.handshake.version` always reads 1.2; the
real version is in `tls.handshake.extensions.supported_version`. Cipher suites are printed as
numbers; add `-o gui.column.format:"Info","%i"` or dissect with `-V` to see names.

Decrypting: `-o tls.keylog_file:keys.log` (key log, any cipher) or, for RSA key exchange only,
`-o "uat:rsa_keys:\"C:/keys/server.key\",\"\""`.

## DNS

```bash
tshark -r file.pcapng -Y "dns.flags.response == 0" -T fields -e frame.time_relative -e ip.src -e dns.qry.name
tshark -r file.pcapng -Y "dns.flags.response == 1" -T fields -e dns.qry.name -e dns.a -e dns.time
tshark -r file.pcapng -Y "dns.flags.rcode != 0" -T fields -e dns.qry.name -e dns.flags.rcode   # 3 = NXDOMAIN
tshark -r file.pcapng -Y "dns" -T fields -e dns.qry.type -e dns.qry.name
```

A slow first call followed by fast ones is often DNS: check `dns.time` and queries that get no
answer at all.

## Oracle TNS

IS adapters and Spring services reach Oracle over TNS, normally on port 1521:

```bash
tshark -r file.pcapng -Y "tns" -T fields -e frame.number -e frame.time_relative -e ip.src -e tns.type
tshark -r file.pcapng -Y 'tns && frame contains "ORA-"' -T fields -e frame.number -e ip.src
tshark -r file.pcapng -d tcp.port==1522,tns -Y tns          # listener on another port
```

TNS types: 1 Connect, 2 Accept, 4 Refuse, 5 Redirect, 6 Data, 11 Resend, 12 Marker. A Refuse
right after Connect is a listener-level problem (unknown service name, ORA-12514); a Redirect to
another port that then gets no SYN-ACK is a firewall that allows 1521 but not the redirected
port. With Native Network Encryption the payload is unreadable, but connect/refuse and timings
still are.

## SMB

```bash
tshark -r file.pcapng -Y "smb2" -T fields -e ip.src -e smb2.cmd -e smb2.filename
tshark -r file.pcapng -Y "smb2.cmd == 8 or smb2.cmd == 9" -T fields -e ip.src -e smb2.filename   # read / write
tshark -r file.pcapng -Y "smb2.nt_status != 0" -T fields -e smb2.filename -e smb2.nt_status
```

Useful for file pollers that read from a share: a `STATUS_ACCESS_DENIED` or
`STATUS_SHARING_VIOLATION` on the file explains a poller that "sees" nothing.
