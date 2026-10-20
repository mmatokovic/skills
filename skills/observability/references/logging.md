# Logging

## Fields every event needs

| Field (ECS name) | Example | Why |
|---|---|---|
| `@timestamp` | `2026-10-20T14:32:15.123Z` | ISO 8601, UTC |
| `log.level` | `ERROR` | filtering, alerting |
| `message` | `Policy finalize failed` | human-readable summary; no data dumps |
| `service.name` | `policy-api` | which app — from `spring.application.name` |
| `service.version` | `1.4.2` | ties errors to a release |
| `service.environment` | `test` | one index can hold several environments |
| `trace.id` / correlation ID | `4bf92f35…` | joins every line of one request across services |

Useful when relevant: `http.request.method`, `url.path`, `http.response.status_code`, `event.duration`, `error.type`, `error.message`, `error.stack_trace`, and business keys that are not personal data (policy number, flow ID).

## Spring Boot setup

Spring Boot 3.4+ has structured logging built in:

```yaml
spring:
  application:
    name: policy-api
logging:
  structured:
    format:
      console: ecs            # or logstash
    ecs:
      service:
        version: ${APP_VERSION:unknown}
        environment: ${ENVIRONMENT:local}
  level:
    root: INFO
```

Keep plain-text console for local runs with a profile (`application-local.yml` without `logging.structured.format.console`). MDC entries are written as extra JSON fields automatically.

## Correlation ID filter

If Micrometer Tracing is on the classpath, `traceId`/`spanId` are already in MDC and propagated on `RestClient`/`WebClient` calls built from the auto-configured builders. To also honour a team header:

```java
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
class CorrelationIdFilter extends OncePerRequestFilter {

    static final String HEADER = "X-Correlation-Id";
    static final String MDC_KEY = "correlationId";

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String id = Optional.ofNullable(request.getHeader(HEADER)).filter(s -> !s.isBlank())
                .orElseGet(() -> UUID.randomUUID().toString());
        MDC.put(MDC_KEY, id);
        response.setHeader(HEADER, id);
        try {
            chain.doFilter(request, response);
        } finally {
            MDC.remove(MDC_KEY);
        }
    }
}
```

Pass the same header on outbound calls (a `ClientHttpRequestInterceptor` reading `MDC.get(MDC_KEY)`). MDC is thread-local: `@Async` and executor tasks need a `TaskDecorator` that copies the MDC context.

## Levels

| Level | Use for | Not for |
|---|---|---|
| `ERROR` | a request or job failed and someone must look | validation failures caused by the client (those are 4xx, `INFO` or `WARN`) |
| `WARN` | unexpected but handled: retry succeeded, fallback used, deprecated call | normal business outcomes |
| `INFO` | startup, one line per business event or request summary | per-loop or per-row detail |
| `DEBUG` | diagnostic detail, off in production | anything you need to read in prod incidents |

## Common mistakes

- Logging and rethrowing — the same stack trace appears three times.
- `log.error("Failed: " + e.getMessage())` — loses the stack trace. Use `log.error("Failed to finalize policy {}", policyNo, e)`.
- String concatenation in log calls — use `{}` placeholders.
- Whole request/response bodies at `INFO` — size, cost and personal data. Log them at `DEBUG`, masked.
- Multi-line messages — break JSON-per-line parsing unless structured logging is on.

## Personal data and secrets

Never log: passwords, tokens, `Authorization` headers, API keys, OIB, card numbers, full names with addresses, health data. Mask at the source (a custom JSON field converter or explicit masking in the log call). Kibana access controls are not a substitute — logs are copied to snapshots and exports.

## Kibana (KQL) patterns

```text
service.name : "policy-api" and log.level : "ERROR"
correlationId : "a1b2c3d4-..."                               # one request across services
trace.id : "4bf92f35..."
http.response.status_code >= 500 and service.name : "policy-api"
error.type : *SQLException*
message : "timeout" and not service.environment : "prod"
event.duration > 2000000000                                  # ECS duration is in nanoseconds (2 s)
```

Workflow for an error: filter on `log.level : "ERROR"` and the service → open one event → take its correlation/trace ID → query by that ID alone over all services to see the whole request.

## Retention and volume

Agree a retention per environment and index (prod longer than test). The cheapest volume reduction is removing noisy `INFO` lines and request-body logging, not sampling errors — never sample `ERROR`.
