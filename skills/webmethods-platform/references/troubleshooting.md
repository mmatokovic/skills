# Troubleshooting — installer and runtime

Covers **§8–§9** — installer hangs and slow IS shutdown.

> Topic-specific troubleshooting lives with its topic: DBCC schema problems in `database.md` (§6.5), API Gateway in `api-gateway.md` (§20.10–20.11).

---

## 8. Installer Troubleshooting

### 8.1 Installer hangs on "Provisioning products..." (stale p2 lock)

Symptom: installer sits indefinitely with 0% CPU/disk/network on all its processes. A `jstack` thread dump of the main Java process shows a worker thread permanently blocked in `Commands.getComponents()` waiting on an object monitor, with zero background job/worker threads active — a genuine deadlock, not a slow download.

Root cause (confirmed via `LastWriteTime`): a stale Eclipse/Equinox **p2 profile lock** file left over from an earlier install session that didn't shut down cleanly:
```
C:\SoftwareAG\{version}\install\profile\p2\org.eclipse.equinox.p2.engine\profileRegistry\minimal.profile\.lock
```

Fix:
```powershell
# 1. Confirm no installer processes are actually running
Get-Process java,javaw,IBM_webMethods_Install_Windowsx64 -ErrorAction SilentlyContinue

# 2. If any are present despite the installer appearing "cancelled", force-kill
Stop-Process -Id <PID> -Force

# 3. Delete the stale lock (safe to remove once confirmed no live process holds it)
Remove-Item "C:\SoftwareAG\{version}\install\profile\p2\org.eclipse.equinox.p2.engine\profileRegistry\minimal.profile\.lock" -Force

# 4. Relaunch the installer fresh
```

> Note: a stale lock is a real but *not sole* cause — even from a genuinely clean state (no processes, no lock file), the "modify existing install" flow (adding a product/feature after the fact) reproduced the identical hang three times. A full uninstall + reinstall with the desired product selection from the start avoided the issue entirely, since every *fresh* install attempt completed the "Provisioning" step without hanging.

### 8.2 Before a full uninstall/reinstall — back up cluster config first

A fresh reinstall resets Terracotta/IS clustering config to defaults. Back up these files from **both** nodes first:
```powershell
$backup = "C:\Temp\pre-reinstall-backup"
New-Item -ItemType Directory -Force $backup
Copy-Item "C:\SoftwareAG\TEST\111\Terracotta\server\wrapper\conf\tc-config.xml" $backup
Copy-Item "C:\SoftwareAG\TEST\111\Terracotta\server\wrapper\conf\wrapper-tsa.conf" $backup
Copy-Item "C:\SoftwareAG\TEST\111\IntegrationServer\instances\default\config\server.cnf" $backup
Copy-Item "C:\SoftwareAG\TEST\111\IntegrationServer\instances\default\config\Caching\SoftwareAG-IS-*.xml" $backup
Copy-Item "C:\SoftwareAG\TEST\111\common\conf\terracotta-license.key" "$backup\terracotta-license-common.key"
Copy-Item "C:\SoftwareAG\TEST\111\Terracotta\terracotta-license.key" "$backup\terracotta-license-tsa.key"
```

### 8.3 Removing leftover Windows services before a clean reinstall

```powershell
# Discover what's registered
Get-Service | Where-Object { $_.DisplayName -match "Terracotta|SoftwareAG|webMethods|Integration Server" } | Select-Object Name, DisplayName, Status

# Stop everything found
Get-Service | Where-Object { $_.DisplayName -match "Terracotta|SoftwareAG|webMethods|Integration Server" } | Stop-Service -Force

# Remove Terracotta's service via its own wrapper script (preferred over generic sc delete)
cd "C:\SoftwareAG\TEST\111\Terracotta\server\wrapper\bin"
.\tsa-service.bat remove

# Generic fallback for any other registered service, once confirmed stopped
sc.exe delete "<ServiceName>"
```
`sc.exe delete` only removes the SCM registry entry — it does **not** stop a running process. Always `Stop-Service`/confirm the process is gone first, or the delete just gets queued as "pending" while the old process keeps holding file locks (which is what causes `C:\SoftwareAG` folder deletion to fail with "folder in use").

---


## 9. IS Shutdown/Restart Slowness

Symptom: shutting down IS via the Windows service takes several minutes (observed: ~7m44s), long enough to look "stuck," tempting a full server reboot — but it does eventually complete on its own if given enough time.

Diagnosis from `server.log` timestamps: the JDBC connection pools (business/adapter pools) shut down almost instantly, then Scheduler task cancellations trickle in with multi-second gaps between each — but the **dominant** cost is a single ~5.5-minute **completely silent gap** between the last `[SCHED] ... has been cancelled` line and the next `WmRoot: Shutdown service` line, with zero log output in between. This pattern (one long silent wait, not many small ones) points to a single blocked/timed-out operation — likely the system JDBC pool (`ISInternal`, now external Oracle instead of embedded Derby) hitting a connection/idle/reap timeout during its own shutdown cleanup, though this was not conclusively proven with a thread dump captured mid-shutdown (recommended next step if this recurs: `jstack` the IS java process during that silent window).

Practical takeaway: don't assume "stuck" from Windows Services alone — confirm via `server.log` whether it's making forward progress before reaching for a full server reboot. Note also §2.2's guidance to run the main IS service as **Manual** startup on clustered nodes — this may be a deliberate mitigation for exactly this kind of slow/ambiguous shutdown behavior during coordinated cluster restarts.

