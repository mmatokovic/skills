# Installation and base configuration

Covers **§2, §3, §10, §16** — base install, migrating configuration from the old server, post-configuration, and other tooling.

**Applies to every environment.**

---

## 2. Base Installation

### 2.1 Prerequisites

- Install **Notepad++** — download in `C:\Install`

### 2.2 Installation steps

1. **Download the Installer** from [Passport Advantage Online](https://www.ibm.com/software/passportadvantage/pao-customer) and paste installer to `C:\Install`
2. **Run the Installer as Administrator.**
3. **Choose Install Location:**
   - Custom folder: `C:\SoftwareAG\{environment}\{version}`
   - Rename Start Menu group to avoid conflicts: `Software AG {environment}`
4. **Select Products** — check all required components (Terracotta only necessary for servers that are in a cluster).

   > **Critical gotcha discovered during the TEST upgrade:** under Database Configuration, there are two very similarly named items — **"Integration Server and Microservices Runtime Database Scripts"** (full DDL, all components/RDBMS types) vs **"Integration Server and Microservices Runtime *Embedded* Database Scripts"** (Derby/embedded-only scope, partial or zero content for several components). Selecting only the Embedded variant was the root cause of nearly every DBCC issue documented in §7. **Check both, or specifically the non-Embedded one.** See §7.1 for full detail.

5. **Instance Configuration:**
   - Set primary port to `5555` (if multiple installations on one server, use a different port) and set the diagnostic port.
   - Set instance name to `default`.
   - Enable "Register Windows service" — **on servers that are in a cluster, manually set startup in Windows services to Manual instead of Automatic** (this is a deliberate operational choice for clustered nodes, distinct from the Terracotta service itself, which *should* auto-start — see §3.3).
6. **Proceed with Installation.**
7. **Add ports to VPN group `asw2`** — open an ISM ticket for the Network team (both Primary and Regular Ports). DEV and TEST both use **`5555` primary / `5651` regular**, on every node — the clustered TEST pair does not vary it per node.

---


## 3. Post-Install Configuration (Migrating Settings from the Old Server)

- **Add third-party (custom) jar files**
  - Copy from the old Software AG directory to `\IntegrationServer\instances\{instance_name}\lib\jars\custom`
  - Also add a missing jar `javax.xml.soap-api-1.3.5` if not already included.
- **Add IS's config directory store** — copy from the old server to `\IntegrationServer\instances\{instance_name}\config`: `globalVariables.cnf`, `acls.cnf`, `acllist.cnf`, `aclmap_sm.cnf`, `aclread.cnf`, `aclwrite.cnf`, `users.cnf`. This is what carries over ACL groups and users from the old environment — no separate manual ACL/user creation step needed.

  > **Access control audit:** an `AccessControlReview.xlsx` spreadsheet documents the resulting access-control configuration in detail — sheets for `Users` (with enabled flag and group memberships), `Groups` (members, allow/deny ACLs), `ACLs` (allow/deny groups, service count), `Services` (service → ACL), plus a full User→Group→ACL→Service cross-reference and a per-service user listing. Useful for verifying the config copy landed correctly, and as a reference when questions come up about who can reach which service.
  >
  > *Location: currently local-only (not yet shared). To be reviewed/extended with PRODUCTION users and ACLs at a later date, then uploaded to the team SharePoint — replace this note with the SharePoint link once that happens.*
- **Add File Adapter access control configuration** — copy to `\IntegrationServer\instances\{instance_name}\packages\wmPublic\config\fileAccessControl.cnf`.
- **Add JDBC Adapters:**
  - Copy the **COConfig** package to `\IntegrationServer\instances\default\packages`.
  - Copy the **mssql**, **oracle**, and **as400** folders to `\IntegrationServer\instances\{instance_name}\packages\WmJDBCAdapter\code\jars`.
- **Allocate more memory** (avoids partial/full service failure) — edit:
  ```
  C:\SoftwareAG\{env}\{version}\IntegrationServer\instances\default\configuration\custom_wrapper.conf
  ```
  ```
  wrapper.java.initmemory=2048
  wrapper.java.maxmemory=4096
  ```
  Start IS through Windows Services (remember to change Startup type to Manual).
- **Configure server logging** — Administration Dashboard → Logs → Logging configuration → Server Logger → Edit Server Logger → expand Integration Server:
  - Disable large-payload logs (they contain base64-encoded files and grow huge): SOAP (`0088`) → **error**, REST (`0166`) → **error**.
  - Date/time format: `yyyy-MM-dd HH:mm:ss.SSS z`
  - Click **Save Changes**.
- **Add all SSL certificates** — copy files to `\IntegrationServer\instances\default\config\security\keystore`, then Security → Keystore, add all certificates manually.
- **Add all External SFTP servers** — copy `sftpServerAliases.cnf` and `sftpUserAliases.cnf` to `\IntegrationServer\instances\{instance_name}\config\sftp`.
- **Change server's Extended Settings** (requires a restart to take effect):

  | Key name | Value | Default value |
  |---|---|---|
  | `watt.server.url.alias.partialMatching` | true | false |
  | `watt.security.ssl.client.ignoreEmptyAuthoritiesList` | true | false |
  | `watt.server.date.suppressPatternError` | true | false |
  | `watt.server.json.encodeDateAs` | `yyyy-MM-dd'T'HH:mm:ss.SSSXXX` | — |
  | `watt.server.threadPool` | 400 (test/prod, per node) / 300 (preprod, per node) | 75 |
  | `watt.server.serverlogRotateSize` | 350MB | — |

- **Deploy util packages to the target server:**
  - Copy **COUtils**, **COUtilsV2**, **COUtilsV003**, **COCDM**, **COCDMV002**, **COCDMV003** from the old server to `\IntegrationServer\instances\{instance_name}\replicate\inbound`.
  - Open IS Packages → Management → **Install Inbound Release**.
  - For COUtils, additionally run (from `\IntegrationServer\instances\{instance_name}\bin`):
    ```
    .\jcode fragall COUtils COUtilsV2 COUtilsV003
    .\jcode makeall COUtils COUtilsV2 COUtilsV003
    ```
- **Activate JDBC Adapters** — on startup all JDBC adapters are suspended by default; set a password for each and save, then click **Enable** for every adapter.

---


## 10. Post-Configuration Odds and Ends

### 10.1 Change the service account for a Windows service

To enable the same user to connect to file polling:
- Open **Services**, right-click a *Software AG Integration Server* service → **Properties**
- **Log On** tab → *This account* → Browse → type `intsvcdev@crosig.hr` → Check Names
- Password is in KeePass and Bitwarden.

### 10.2 Log File Archiver

Install the **Log File Archiver** script:
- Clone/move [Log File Archiver](https://bitbucket.org/crosig/webmethods-logfile-archiver) to `C:\Install` on the target server.
- Open **CMD (not PowerShell)** as Administrator:
  ```
  cd C:\Install\webmethods-logfile-archiver
  install.bat C:\SoftwareAG\{env}\{version}
  ```
- If the instance name is not `default`, configure `build_log-archive.xml` under `C:\SoftwareAG\{environment}\{version}\tools\operations\logArchiver`:
  ```xml
  <!-- Name of Integration Server instance (only for v9.6 or higher) -->
  <property name="instancesNameIS" value="{instance_name}" />
  ```
- Try the first run:
  ```
  cd C:\SoftwareAG\{environment}\{version}\tools\operations\logArchiver
  run_log-archive.bat
  ```
  Look for `BUILD SUCCESSFUL`.
- **Task Scheduler:** Import task → `IntegrationServerCleanup.xml` (from repo). Under Actions, edit the path to:
  ```
  C:\SoftwareAG\{env}\111\tools\operations\logArchiver\run_log-archive.bat
  ```
  Click OK, provide the `intsvcdev` password (KeePass/Bitwarden) when prompted. Verify it appears in Task Scheduler Library.

Common Task Scheduler error codes:

| Code | Meaning | Typical Cause |
|---|---|---|
| `0x8007010B` | The directory name is invalid | Wrong `Start in`/working directory, missing folders, path typo |
| `0x80070005` | Access is denied | User running the task lacks permissions (NTFS, traversal rights, network access) |
| `0x41301` | Task is currently running | Batch file waiting for input, hung process, task not returning control |
| `0x0` | Success | Completed with no errors |

### 10.3 JVM Metrics

IS UI → Dashboard → click the (easy to miss) invisible button on the far right → **Dashboard configuration**. Metrics can be disabled entirely or reconfigured — do this if CPU spikes are causing performance issues.

---


## 16. Install Other Tools

### 16.1 Wireshark

- Install [Wireshark](https://www.wireshark.org/download.html) in `C:\tools\WiresharkPortable64`.
- Download and install [npcap](https://npcap.com/#download).
- Verify it runs.

---


---

## Shared-server environments (UAT + PREPROD)

UAT and PREPROD **share one Windows server for Integration Server and one for Universal Messaging**. Every other installation gets its own server.

Nothing below has been decided yet — it is deliberately left to whoever installs those environments. Each item is a real collision the shared server forces. **Record the chosen values here once UAT is built.**

| Decision | Why it is forced | Chosen value |
|---|---|---|
| IS primary and diagnostic ports | Both instances cannot use `5555` (§2.2 step 5) | *TBD* |
| UM NHP interface port | Both realms cannot use `9000` (§13.1) | *TBD* |
| JVM heap per IS instance | §3 sets `maxmemory=4096`; two instances is 8 GB of heap before the OS | *TBD* |
| Windows service names | Must differ per instance | *TBD* |
| Start Menu group names | §2.2 step 3 — must differ to avoid conflicts | *TBD* |
| Log archiver scheduled task | One task per instance, each with its own `run_log-archive.bat` path (§10.2) | *TBD* |
| Filebeat inputs | One agent, two `filestream` inputs with distinct `id` values (§12) | *TBD* |

> The "UM port is 9000" statement in §13 holds **per server**. A shared UM host forces one of the two environments off it.
