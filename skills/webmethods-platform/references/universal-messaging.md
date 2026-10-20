# Universal Messaging

Covers **§13** — install, cluster, and connecting Integration Server.

> Cluster creation (§13.5) is **TEST and PROD only**. Single-node environments install one realm and skip it.
> On the shared UAT/PREPROD server the NHP port cannot be 9000 for both — see the decisions block in `installation.md`.

---

## 13. Universal Messaging — Install, Cluster, and IS Connection

A two-node UM cluster (master/slave) providing messaging for the clustered IS pair. Note this is a **second, independent cluster** — the UM cluster and the IS/Terracotta cluster (§4–5) share nothing and are configured separately.

### 13.1 Ports, protocols and naming

| Item | TEST value | Notes |
|---|---|---|
| Install root | `C:\SoftwareAG\TEST\111\` | same convention as IS |
| NHP interface port | `9000` | TEST value. **DEV runs `9005`** — the port is per-environment, not a platform constant (§13.9) |
| Cluster name | `UM_TEST_Cluster` | |
| Realm names | `umtest1` (um3), `umtest2` (um4) | |

Realm names must be **distinct per node** — they are node identities within the cluster, not a shared alias. Getting this wrong means the two nodes can't be assembled into a cluster.

Protocol prefixes are not interchangeable:

| Prefix | Used for |
|---|---|
| `nhp://` | Enterprise Manager admin connections |
| `nsp://` | IS → UM realm connections |

### 13.2 Decide the install strategy first: migrate vs. new install

Two mutually exclusive approaches, and the choice has consequences:

- **New installation** — a clean realm with no old objects. **This is the approach TEST used and the one to follow** (installer Purpose: *New installation*).

- **Migrate** from the old environment — carries across the old realm's channels, queues, durables and ACLs. Recorded here as an alternative only; it is not the path TEST took. Run CMD as Administrator:
  ```
  C:\SoftwareAG\{env}\{version}\UniversalMessaging\tools\migrate\migrate.bat -srcDir full_path_to_{old_SoftwareAG_directory|ZIP file}
  ```
  Press **Y** to export settings, then confirm the migrated settings landed by checking `nirvana.log`. See [IBM's UM upgrade instructions](https://www.ibm.com/docs/en/webmethods-installer/10.15.0?topic=premises-upgrade-universal-messaging).

> **Open question from the TEST build:** because TEST took the new-install path, no channels/queues/durables were carried over from 10.11. Anything the deployed packages expect to already exist on the realm has to be created — either by the packages themselves on first connect, or manually. Verify this against the old TEST realm's object list before declaring UM done, and record the answer here.

### 13.3 Install Universal Messaging (on BOTH UM nodes)

1. Launch the IBM webMethods Installer.
2. Under **Universal Messaging**, tick:
   - Realm Server 11.1
     - **Broker to UM Migration Utility** — gets checked automatically along with Realm Server. Not needed; **uncheck it**.
   - Client Libraries 11.1
   - Instance Manager 11.1
   - Enterprise Manager 11.1
   - Template Applications 11.1 — *keep it, it's a Realm Server dependency*
3. Under **Platform Manager Plug-ins**, tick **Universal Messaging Plug-in 11.1**.
   > Despite §1's note that this stack runs without Command Central/Platform Manager, this plug-in is still part of the UM selection. Leave it ticked.
4. On the Universal Messaging configuration screen:
   - Purpose: **New installation** (or migrate — see §13.2)
   - **Create Server Instance**: checked
   - NHP interface binding: `ALL`
   - NHP interface port: `9000`
   - Realm server name: **distinct per node** — `umtest1` on um3, `umtest2` on um4
   - Configuration: **webMethods suite use cases (large messages, transactions, persistence)**
   - **Register Windows service**: checked
5. Repeat on the second node.

> Unlike the IS service (§2.2 step 5), the UM realm service **should** be set to Automatic startup — see §13.4. UM is infrastructure the IS nodes depend on, not a clustered peer that needs coordinated manual starts.

### 13.4 Verify realm and service (on BOTH UM nodes)

1. **Services** → find `Software AG Universal Messaging 11.1...` (sorted under **S**).
2. If **Register Windows service** was missed during the install (§13.3 step 4), register it manually from **CMD as Administrator**:
   ```
   cd C:\SoftwareAG\{env}\111\UniversalMessaging\server\{realm}\bin
   registerService.bat
   ```
3. Set startup to Automatic and start it:
   ```powershell
   Set-Service -Name "um_realm_{realm}*" -StartupType Automatic
   Start-Service -Name "um_realm_{realm}*"
   ```
4. Confirm it's listening:
   ```powershell
   netstat -ano | findstr 9000
   ```
   Expect `LISTENING` on 9000.
5. Confirm clean startup in `C:\SoftwareAG\{env}\111\UniversalMessaging\server\{realm}\data\nirvana.log` — expect `Started Nirvana Realm in ... ms`.

### 13.5 Create the UM cluster (ONCE, from a single Enterprise Manager)

Like DBCC (§6.2), this is a create-once operation against shared state — not a per-node step.

1. Launch Enterprise Manager:
   ```
   C:\SoftwareAG\{env}\111\UniversalMessaging\java\{realm}\bin\nenterprisemgr
   ```
2. Right-click **Realms** → **Connect to a Realm** → RNAME `nhp://crsintdev2um3.crosig.group:9000`. Leave username/password blank → OK.
3. Repeat for node 2: `nhp://crsintdev2um4.crosig.group:9000`.
4. Confirm **both** realms show connected (green) in the tree.
5. Confirm node-to-node reachability on 9000 in **both** directions:
   ```powershell
   Test-NetConnection -ComputerName crsintdev2um4.crosig.group -Port 9000
   ```
6. Right-click **Clusters** → **Create Cluster**, name it `UM_{ENV}_Cluster`.
7. Move **both** realms into **Cluster Members** → OK.
8. Verify in the Cluster Members panel: one **Master**, one **Slave**, both **OnLine**.

### 13.6 Connect IS to the UM cluster (on BOTH IS nodes)

> Per-instance config — it does **not** replicate through the IS cluster, despite the IS nodes being clustered. Same caveat as the JDBC pool/functional alias work in §7.

1. From each IS node, confirm reachability to both UM nodes:
   ```powershell
   Test-NetConnection -ComputerName crsintdev2um3.crosig.group -Port 9000
   Test-NetConnection -ComputerName crsintdev2um4.crosig.group -Port 9000
   ```
2. IS Admin UI → **Settings → Messaging → webMethods settings** → **IS_UM_CONNECTION**.
3. **Realm URL** — both realms, comma-separated, using `nsp://`:
   ```
   nsp://crsintdev2um3.crosig.group:9000,nsp://crsintdev2um4.crosig.group:9000
   ```
4. Confirm **Enable Follow the Master** is ticked for Producers and Consumers → **Save Changes**.
5. Confirm **Client Prefix** is distinct from the other IS node. Auto-generated prefixes differ by default, but check rather than assume — two IS nodes sharing a prefix will collide on the realm.
6. On the list page, in the **Enabled** column click **No** so it flips to **Yes**.

### 13.7 JMS / JNDI (on BOTH IS nodes)

> Per-instance config — do it on esb3 **and** esb4. Configure in dependency order: **JNDI provider → JMS alias → UM**.

#### 13.7a JNDI provider

1. IS Admin → **Settings → Messaging → JNDI settings**.
2. `DEFAULT_IS_JNDI_PROVIDER` → **Edit JNDI Provider Alias**.
3. Confirm **Initial Context Factory** = `com.pcbsys.nirvana.nSpace.NirvanaContextFactory`.
4. Set **Provider URL** — both realms, comma-separated, `nsp://`, matching §13.6:
   ```
   nsp://crsintdev2um3.crosig.group:9000,nsp://crsintdev2um4.crosig.group:9000
   ```
   Leave **Provider URL Failover List** empty — the comma-separated URL already provides failover.
5. Save.

#### 13.7b JMS connection alias

1. IS Admin → **Settings → Messaging → JMS settings**.
2. `DEFAULT_IS_JMS_CONNECTION` → **Edit JMS Connection Alias**.
3. Confirm:
   - Create Connection Using: `JNDI LOOKUP`
   - JNDI Provider Alias: `DEFAULT_IS_JNDI_PROVIDER`
   - Connection Factory Lookup Name: `local_um`
4. Set **Create Administered Objects On Demand (Universal Messaging)** = **Yes**. This auto-creates the `local_um` connection factory on the UM side — no manual step needed in Enterprise Manager.
5. Confirm **Enable Follow the Master** = Yes → Save.
6. On the list page, flip **Enabled** to **Yes**.

#### 13.7c Verify

1. Enterprise Manager → realm → **JNDI** tab → NameSpace → **Connection Factories** → `local_um` should be present.
2. `PE_NONTRANSACTIONAL_ALIAS` (Process Engine) — enable **only** if this environment runs BPM/Process Engine. Otherwise leave it disabled.

#### 13.7d JMS *and webMethods* triggers — leave DISABLED until the environment is live

> ⚠️ **A running JMS or webMethods trigger is a live consumer.** It will pull and process real messages the moment it connects — potentially before the environment is ready, and potentially against production partners or the wrong database.

1. IS Admin → **Settings → Messaging → JMS triggers** *and* **webMethods triggers**. Check on **both** nodes — trigger state is per-instance and does not replicate.
2. Set any trigger showing **Running** to **Disabled** via the State column.
3. Before ever re-enabling a trigger, verify its downstream service targets (DB, partner endpoints) point at *this* environment.

#### 13.7e Master password expiration

Not part of the UM runbook — carried over from the Confluence procedure and still applicable:

Security → **Outbound passwords** → Update Expiration Interval → set to **0 days** → Update. Do this on **both** IS nodes.

### 13.8 Verify JNDI configuration

1. In Enterprise Manager, check under **Realms** that both UM servers are set up correctly. One client node should appear **per IS node**, each with its own client prefix.
2. Cluster status: one Master, one Slave, both OnLine.
3. Both UM realm services set to **Automatic** on both hosts.

**Failover test (recommended, not yet run on TEST):**
1. Stop the master realm service (`umtest1`).
2. Confirm `umtest2` becomes Master and both IS nodes stay connected or reconnect.
3. Restart `umtest1`; confirm it rejoins as Slave.

### 13.9 Superseded values from the older Confluence runbook

Everything above comes from the as-built UM cluster runbook, which is **authoritative for this section**. An earlier version of §13 was derived from the Confluence page, which was written for a single-node, migrate-based install and differs on the points below. They're listed so that anyone who encounters the old values elsewhere recognises them as replaced — do not use the left-hand column.

> **The `Port` row is the exception**, and it was previously documented here as an error. It isn't: the NHP port is genuinely per-environment. DEV listens on `9005`, TEST on `9000`. Read that row as "TEST's value differs from DEV's", not "the old value was wrong".

| Item | Superseded value | Correct value | Notes |
|---|---|---|---|
| Port | `9005` | **`9000` on TEST** | Entered as the *NHP interface port* during install (§13.3). **Not a correction — the port is per-environment.** DEV genuinely runs `9005`: verified on `crsintdev2um1`, listening with live IS connections from the DEV IS host. `9000` is TEST's value. Check the target environment before assuming either. |
| Strategy | migrate from old install | **new installation** | §13.2. Migrate stays documented as an alternative, but is not the standard path. |
| IS → UM protocol | `nhp://` | **`nsp://`** | `nhp://` remains correct for Enterprise Manager admin connections — the correction applies only to the IS → UM realm connection. |
| Realm name | `um{env}` | **distinct per node** (`umtest1` / `umtest2`) | The single-realm convention doesn't survive clustering; realm names are node identities. |
| JMS Connection Factory | look up an existing CF via **Test Lookup**, e.g. `{env}_um: javax.jms.ConnectionFactory` | **`local_um`**, auto-created via *Create Administered Objects On Demand* | §13.7b. Different approach, not just a different name — IS creates the CF rather than binding to one that already exists. |
| JNDI Provider URL | single realm | **both realms, comma-separated, `nsp://`** | §13.7a. Failover List stays empty. |

> Note on §13.7e: the master-password step is **not** a conflict — the UM runbook simply doesn't cover it, and it's still applicable. Retained from the Confluence procedure for that reason.

