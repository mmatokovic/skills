# Log shipping — Filebeat and Kibana

Covers **§12**.

> On the shared UAT/PREPROD server one Filebeat instance needs two `filestream` inputs with distinct `id` values, not the single input shown here.

---

## 12. Log Shipping — Filebeat / Kibana

Version in use: **Filebeat 9.4.4**, installed under:
```
C:\Program Files\Elastic\Beats\9.4.4\filebeat\
```

### 12.1 `filebeat.yml` doesn't ship by default in this version

Only `filebeat.example.yml` and `filebeat.reference.yml` are present. Copy the example to create the working config:
```powershell
Copy-Item "C:\Program Files\Elastic\Beats\9.4.4\filebeat\filebeat.example.yml" "C:\Program Files\Elastic\Beats\9.4.4\filebeat\filebeat.yml"
```

### 12.2 Input type: `filestream`, not `log`

The shipped example only demonstrates `filestream` — the older `log` input type is deprecated in favor of `filestream`, which additionally requires a unique `id` field.

### 12.3 Complete working config

```yaml
###################### Filebeat Configuration - {ENV} #########################

#=========================== Filebeat inputs =============================

filebeat.inputs:

- type: filestream

  id: integration-server-log

  enabled: true

  paths:
    - C:\SoftwareAG\{env}\111\IntegrationServer\instances\default\logs\server.log

  fields:
    env: {env}

#============================= Filebeat modules ===============================

filebeat.config.modules:
  path: ${path.config}/modules.d/*.yml
  reload.enabled: false

#==================== Elasticsearch template setting ==========================

setup.template.settings:
  index.number_of_shards: 1

#============================== Kibana =====================================

setup.kibana:

#================================ Outputs =====================================

#----------------------------- Logstash output --------------------------------
output.logstash:
  hosts: ["crsintegra:5044"]

#================================ Processors =====================================

processors:
  - add_host_metadata: ~
  - add_cloud_metadata: ~
  - add_docker_metadata: ~
  - add_kubernetes_metadata: ~

#================================ Logging =====================================

#logging.level: debug
#logging.selectors: ["*"]
```

> **Critical gotcha:** the example file ships with `output.elasticsearch: hosts: ["localhost:9200"]` **active by default**. Only one output can be configured at a time — leaving both active causes Filebeat to fail to start. The real output target for this org is **Logstash at `crsintegra:5044`**, not Elasticsearch directly.

### 12.4 Registering and starting the service

```powershell
# Only needed if not already registered on this box
cd "C:\Program Files\Elastic\Beats\9.4.4\filebeat"
.\install-service-filebeat.ps1
Start-Service filebeat

# Otherwise, after editing filebeat.yml:
Restart-Service filebeat
```

### 12.5 Verifying it's actually working

```powershell
Get-Service filebeat
Get-ChildItem "C:\Program Files\Elastic\Beats\9.4.4\filebeat\logs"
Get-Content "C:\Program Files\Elastic\Beats\9.4.4\filebeat\logs\filebeat-{date}.ndjson" -Tail 50
```

Logs are structured JSON (`.ndjson`). Confirm:
- `Starting input (ID: ...)` for the filestream input
- `Connection to backoff(async(tcp://crsintegra:5044)) established`
- Non-zero `events_pipeline_published_total` / `output.events.acked` in the periodic metrics snapshot (proves lines are actually being read and shipped, not just that the service is "running")

A warning like *"unable to load the ingest pipelines because the Elasticsearch output is not configured"* is expected and harmless when using a Logstash output — safe to ignore.

Repeat the same config (path/hostname adjusted) on the second node.

