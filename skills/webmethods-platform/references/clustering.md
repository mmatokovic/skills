# Clustering — Terracotta and Integration Server

Covers **§4–§5**.

> **TEST and PROD only.** DEV, UAT and PREPROD run a single IS node and skip this entirely.

---

## 4. Clustering — Part 1: Terracotta Server Array (BigMemory Max)

### 4.1 Place the license file (both locations, both hosts)

Copy from the old server to:

| Consumer | Location |
|---|---|
| Integration Server (client-side check) | `C:\SoftwareAG\{env}\111\common\conf\terracotta-license.key` (read via `watt.server.terracotta.license.path`) |
| Terracotta Server process (TSA) | `C:\SoftwareAG\{env}\111\Terracotta\terracotta-license.key` (read by the TSA process itself) |

### 4.2 Topology config — `tc-config.xml` (both hosts, identical content)

Path: `C:\SoftwareAG\{env}\111\Terracotta\server\wrapper\conf\tc-config.xml`

Replace the shipped single-node template with a two-node definition. Server `name` attributes must match each host's actual Windows hostname (`$env:computername`), determined empirically rather than assumed:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tc:tc-config xmlns:tc="http://www.terracotta.org/config">
  <tc-properties>
    <property name="ehcache.storageStrategy.dcv2.perElementTTITTL.enabled" value="true"/>
  </tc-properties>
  <servers>
    <server host="{host_node1}" name="{name_node1}">
      <data>../work/terracotta/server-data</data>
      <logs>../work/terracotta/server-data</logs>
      <tsa-port>9510</tsa-port>
      <tsa-group-port>9530</tsa-group-port>
      <offheap>
        <enabled>true</enabled>
        <maxDataSize>512m</maxDataSize>
      </offheap>
    </server>
    <server host="{host_node2}" name="{name_node2}">
      <data>../work/terracotta/server-data</data>
      <logs>../work/terracotta/server-data</logs>
      <tsa-port>9510</tsa-port>
      <tsa-group-port>9530</tsa-group-port>
      <offheap>
        <enabled>true</enabled>
        <maxDataSize>512m</maxDataSize>
      </offheap>
    </server>
    <restartable enabled="true"/>
  </servers>
  <clients>
    <logs>%(com.softwareag.tc.client.logs.directory)</logs>
  </clients>
</tc:tc-config>
```

> `tsa-port 9510` is the classic BigMemory Max port, distinct from the dead TerracottaDB dynamic-config port `9410`.
>
> **Error hit during TEST setup:** `You have specified server name 'X' which does not exist in the specified tc-config file.` Cause: the wrapper's `SERVER_NAME` substitution didn't resolve to what was in `tc-config.xml`. Fix: rename the `<server name="...">` entries to match the actual hostname, rather than fighting the substitution mechanism.

### 4.3 Install and start the Windows service (run on each host)

BigMemory Max ships its own Java Service Wrapper — no third-party wrapper (e.g. NSSM) required:

```powershell
cd "C:\SoftwareAG\{env}\111\Terracotta\server\wrapper\bin"
.\tsa-service.bat install
.\tsa-service.bat start
.\tsa-service.bat status
```

Start one node first, confirm it's healthy, then start the second node.

### 4.4 Set the Terracotta service to auto-start on boot (run on each host)

```powershell
sc.exe config TerracottaServerArray start= auto
sc.exe qc TerracottaServerArray
```

Also edit `wrapper-tsa.conf` (same folder as `tc-config.xml`), changing:
```
wrapper.ntservice.starttype=DEMAND_START
```
to:
```
wrapper.ntservice.starttype=AUTO_START
```

> Note the distinction from §2.2 step 5: the **Terracotta/TSA service** should auto-start, while the **main IS Windows service itself** on clustered nodes should be set to **Manual** startup — these are two different services with different intended startup behavior.

### 4.5 Verify TSA is healthy

Check `C:\SoftwareAG\{env}\111\Terracotta\server\wrapper\logs\wrapper-tsa.log`:

- First node (started first) should show: `Becoming State[ ACTIVE-COORDINATOR ]` and `Terracotta Server instance has started up as ACTIVE node ... successfully`.
- Second node should show: `NodeID[...] joined the cluster` → `Moved to State[ PASSIVE-UNINITIALIZED ]` → `Moved to State[ PASSIVE-STANDBY ]`.

---


## 5. Clustering — Part 2: Enable IS Clustering

### 5.1 Edit `server.cnf` on both hosts

Path: `C:\SoftwareAG\{env}\111\IntegrationServer\instances\default\config\server.cnf`

```
watt.server.cluster.aware=true
watt.server.cluster.name={env}_Cluster
watt.server.cluster.tsaURLs={host_node1}:9510,{host_node2}:9510
```

Leave `watt.server.cluster.action.errorOnStartup=standalone` as-is (safe fallback). Fresh installs ship with `watt.server.cluster.aware=false` and no `tsaURLs`/`cluster.name` set — always confirm the live file's actual state before editing rather than assuming.

### 5.2 Edit the three cache manager XML files on both hosts

Path: `C:\SoftwareAG\{env}\111\IntegrationServer\instances\default\config\Caching\`
Files: `SoftwareAG-IS-Core.xml`, `SoftwareAG-IS-ART.xml`, `SoftwareAG-IS-WMN.xml`

These are genuine legacy **Ehcache 2.x** config files (IS reads them via internal `CacheManagerConfig`/`CacheManagerReader` classes) — not the Ehcache 3 `multi:configurations` schema.

For each file, two changes:
1. Add right after `<diskStore .../>`:
   ```xml
   <terracottaConfig url="{host_node1}:9510,{host_node2}:9510"/>
   ```
2. On every `<cache>` block, change `<terracotta clustered="false" ...>` to `clustered="true"`, **and** change the sibling `<persistence strategy="none"/>` (or `"localtempswap"`) to `<persistence strategy="distributed"/>`.

> **Error hit:** `NONE persistence strategy isn't supported for a clustered Terracotta cache`. The persistence-strategy change is mandatory — Ehcache 2 throws this if `clustered="true"` is set without also switching to `strategy="distributed"`.

### 5.3 Restart IS on both nodes

Check `server.log` for clean cache-manager startup (no `CacheException`/parsing errors), then confirm Admin UI login works.

### 5.4 Check cluster membership

IS Administrator → **Settings → Clustering**. At this point you may still see `Clustering Status: Enabled`, `Cluster Online: Yes` (good) but `Unable to create or join the cluster` / `No Cluster Hosts`. `server.log` will show:
```
[ISS.0033.0167E] The ISInternal functional alias on the JDBC Pools page must be configured to use
an external database in order to join a cluster. Clustering has been disabled.
```
This confirms the Terracotta/cache layer is correct — the sole remaining blocker is `ISInternal` still pointing at the embedded (Derby) database.

### 5.5 Open ISM ticket for DBA team

Request a **new, empty** Oracle schema/user per environment — do **not** share the old environment's schema (two IS installs on one schema would collide on scheduler/document-history/xref data).

Example ticket text (Croatian, as used in practice):

> *Potrebno je otvoriti nove database usere za {env} okruženje zbog potrebe upgradea webMethodsa na novi server.*
>
> *Database useri:*
> - **WM_111_IS_{env}_ISCOREAUDIT**
> - **WM_111_IS_{env}_ISINTERNAL**
>
> *Baza:*
> - *{host}:{port}@{database}*
>
> *Novi useri bi trebali imati ista prava kao i postojeći useri* **WM_1011_IS_{env}2_ISCOREAUDIT** *i* **WM_1011_IS_{env}2_ISINTERNAL***. Prilikom kreiranja novih usera potrebno je otvoriti praznu database shemu, s novim tablespaceom, bez kopiranja postojećih tablica s 10.11 verzije (WM_1011) - taj dio odrađuje Integracijski tim.*

(Translation of the key constraint: new users need the same privileges as the existing 10.11-era users; the schema/tablespace must be created empty, without copying old 10.11 tables — table creation is the Integration team's responsibility, done via DBCC below.)

