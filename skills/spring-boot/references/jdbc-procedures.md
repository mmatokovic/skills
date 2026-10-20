# JDBC Stored Procedure Adapters (Oracle)

Some services call Oracle stored procedures through `JdbcTemplate` instead of JPA, usually
when migrating a legacy (webMethods / OLDLEGACYCORE) service. The adapter lives in `infra/`
and implements a domain port. These are the things reviewers keep catching.

## Transactions — `@Transactional(readOnly = true)` on the adapter method

Hikari pools usually run with `auto-commit=false`. Without a Spring transaction, the pool
has to make an extra roundtrip to end the transaction when the connection goes back to it.

```java
@Override
@Transactional(readOnly = true)
public HouseholdSearchResponse searchHousehold(HouseholdSearchRequest params) { ... }
```

- The method must be `public` and called from another bean, not from inside the same class (ArchUnit `ProxyRule`).
- **Behavior change:** Spring commits at the end of the method. Before, Hikari rolled back
  when the connection went back to the pool. If the procedure writes anything (an audit or
  log table, say), those writes are now kept. Check with the DB owner.

## LOBs — free them, read them once

A `Clob`/`Blob`/`Array` returned from a procedure is a temporary LOB in Oracle's temp
tablespace. It lives until the **session** ends, not the connection, and pooled sessions
almost never end. Always free it in `finally`:

```java
var clob = cs.getClob(2);
try {
    var json = clob != null ? clob.getSubString(1, (int) clob.length()) : null;
    // log, check result, parse from json
} finally {
    if (clob != null) {
        clob.free();
    }
}
```

Read the LOB once (`getSubString`) and parse the resulting `String`. Don't read it once for
logging and again through `getCharacterStream()` to parse.

## Retry on Oracle error codes — walk the cause chain

To retry transient errors (ORA-04068/04061/04065/06508, "package state discarded"), you need
the vendor code from the `SQLException`. **Don't use `getMostSpecificCause()` / root cause.**
With ojdbc the root cause is `oracle.jdbc.OracleDatabaseException`, which is *not* an
`SQLException`. The predicate never matches, and the retry silently never fires in production.
Unit tests built on `new SQLException(msg, state, code)` won't catch this.

```java
// ❌ never matches against a real ojdbc exception
dae.getMostSpecificCause() instanceof SQLException sql

// ✅ first SQLException in the chain
private static @Nullable SQLException findSqlException(Throwable ex) {
    for (Throwable cause = ex; cause != null; cause = cause.getCause()) {
        if (cause instanceof SQLException sql) {
            return sql;
        }
    }
    return null;
}
```

Add a test where the `SQLException` has a non-SQL cause underneath it. Only retry
idempotent or read-only calls.

## Naming — adapter vs service methods

The adapter method is named after the procedure it calls (`p_pretrazi_kucanstvo` →
`searchHousehold`). The service method is named after the operation the API exposes
(`getHousehold`). One service operation often calls 2–3 procedure adapters, so the names
don't need to match. Say that in the PR if a reviewer asks.
