# webMethods Service Catalog

This directory contains JSON files that describe the service contracts (input and output signatures) for built-in webMethods Integration Server services. The services are organized by functional category, such as `STRING`, `MATH`, `JDBC`, `JSON`, and `XML`.

The webmethods-service skill uses them to look up what a built-in `pub.*` service invoked by a flow takes and returns, so its Java replacement keeps the same semantics. Grep for the full service name, e.g. `grep -l '"pub.string:padLeft"' *.json`. Source: IBM webMethods Integration Server 12.1 built-in services reference.
