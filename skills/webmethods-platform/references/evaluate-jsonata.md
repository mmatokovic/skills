# evaluate.js — JSONata evaluation service

Covers **§11**. Runs on OpenShift, not on the IS hosts.

---

## 11. evaluate.js — JSONata Evaluation Service (OpenShift Deployment)

### 11.1 What it is

> This is one of two OpenShift-hosted components in the stack — see also **§20, API Gateway**, which runs on the same cluster under a different namespace convention (`wm-{env}` rather than `int-{env}`) and is deployed with Helm rather than Import-from-Git.

A lightweight Node.js/Express HTTP API for evaluating JSONata expressions, called by webMethods IS flow services via HTTP POST. Repo: `https://bitbucket.org/crosig/evaluate/src/main/` (SSH clone: `ssh://bitbucket.org/crosig/evaluate.git`). Runs exclusively on OpenShift, not on the IS servers themselves.

Code is already container-ready — `jsonata`/`express` in `dependencies`, `node-windows` correctly scoped under `devDependencies` (skipped in production installs), `"start": "node evaluate.js"` script present, app reads `process.env.PORT` (falls back to `3000`), and a `GET /api/health` endpoint already exists — useful for OpenShift health probes.

### 11.2 Deployment steps

1. Log into **OpenShift**, select project **int-{env}**, switch to **Developer view**.
2. **Copy the SSH source secret from the lower environment** (e.g. dev → test) rather than generating a new key — the private key is already registered as a Bitbucket repository access key, reusable across environments:
   - In the **lower** environment: Secrets → open `repo-at-bitbucket` → **Reveal values** → copy the `ssh-privatekey` value.
   - In the **new** environment: Secrets → **Create** → create `repo-at-bitbucket` with that same `ssh-privatekey` value.
   - *(If this alone still produces `Host key verification failed`, also copy across the secret's `known_hosts` value the same way, or generate it fresh via `ssh-keyscan bitbucket.org` — this wasn't needed in practice once the secret was copied correctly, but is a documented fallback.)*
3. **+Add** → **Import from Git**. Git Repo URL: `ssh://bitbucket.org/crosig/evaluate.git`.
4. Builder Image: **Node.js**, version `20-minimal-ubi8`.
5. Application/Name: `evaluate` for both.
6. Resources: **Deployment**.
7. Advanced Options: Target Port `3000`, check **Create a route**.
8. Click **Create** — OpenShift builds and deploys automatically; watch Topology for the build to complete and a pod to appear running.
9. **Add Deployment environment variable**: `PORT` = `3000`. This must be set on the **Deployment** resource (Topology → click app icon → Environment tab), *not* the BuildConfig — the BuildConfig's Environment tab only affects build-time variables, not the running container. Easy to add it to the wrong resource by mistake since both have an identically named "Environment" tab.
10. **Actions → Add Health Checks:**
    - Readiness Probe: HTTP GET, path `/api/health`, port `3000`
    - Liveness Probe: HTTP GET, path `/api/health`, port `3000`
11. **Configure Route**
    - Edit Route and set **Insecure traffic** to `Allow` 
12. Verify:
    ```bash
    curl -X POST http://evaluate-int-{env}.apps.openshiftdev.crosig.group/api/evaluate -H "Content-Type: application/json" -d '{"inputJson": "", "expression": "$sum([1,2,3])"}'
    ```
    Expect `6` back.
13. **For future code changes:** push to Bitbucket as normal, then Builds → the BuildConfig → Actions → **Start Build** to rebuild and redeploy.
14. **Point IS at the new host:** IS UI → Settings → Global variables → `crosig.nodejs.host` — edit to the correct host for this environment `http` route.

### 11.3 Notes

- Request body size limit is 50 MB (`express.json({ limit: '50mb' })`).
- No IP whitelist is currently enabled on the endpoint — the codebase has no such block despite older documentation referencing one; worth reconsidering since the app is now reachable via an OpenShift Route rather than a private Windows server.
- Deployment steps are also documented directly in the repo's own `README.md` ([bitbucket.org/crosig/evaluate](https://bitbucket.org/crosig/evaluate)), kept in sync with this document.
- **Historical context:** before the OpenShift migration, `crosig.nodejs.host` pointed directly at the Windows service (e.g. `http://crsintdevesb1:3000` for DEV) instead of an OpenShift route. If troubleshooting an environment that still seems to be calling the old Windows-hosted `evaluate.js`, check this global variable first.

