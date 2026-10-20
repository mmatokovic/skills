# wireshark-analysis

Analyse network packet captures with **tshark** (Wireshark's CLI engine) directly from Claude — no GUI needed. Read PCAP files, apply display filters, extract fields, follow streams, and generate traffic statistics entirely from the terminal.

## Prerequisites

### 1. Install tshark and add it to PATH

tshark ships with **Wireshark**. During the Wireshark installer on Windows, check **"TShark"** under the component list and check **"Add Wireshark to the system PATH"**.

To verify after install (open a new terminal):

```
tshark --version
```

If the command is not found, add Wireshark's directory to PATH manually:

**Windows** — open *System Properties → Environment Variables → Path* and add:
```
C:\Program Files\Wireshark
```

Then open a new terminal and re-run `tshark --version`.

### 2. Allow tshark in Claude permissions

So Claude can run tshark commands without prompting every time, add the permission to your user settings (`~/.claude/settings.json`):

```json
"Bash(tshark:*)"
```

Or run `/permissions` in Claude and add `Bash(tshark:*)` to the allow list.

### 3. Live capture

Reading a capture needs nothing more. Capturing live on Windows also needs **Npcap** (offered by
the Wireshark installer) and a terminal started **as Administrator**. On a server, agree the
capture with its owner first, and use a capture filter and a ring buffer — `SKILL.md` shows how.

## Layout

```
wireshark-analysis/
├── SKILL.md                 # workflow: find tshark, isolate the stream, diagnose, HTTPS limits, live capture
└── references/
    ├── commands.md          # filters, fields, streams, statistics, capture options, export, output formats
    ├── protocols.md         # HTTP, TLS, DNS, Oracle TNS, SMB
    └── security.md          # authorised security analysis
```
