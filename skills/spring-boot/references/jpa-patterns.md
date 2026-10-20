# Spring Data JPA

## Entity Conventions

```java
@Entity
@Table(name = "orders")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED) // JPA requires no-arg, hide from callers
public class Order {

    @Id
    @GeneratedValue(strategy = GenerationType.Long)
    @Column(updatable = false, nullable = false)
    private Long id;

    @Column(nullable = false)
    private String customerEmail;

    @Enumerated(EnumType.STRING) // always STRING, never ORDINAL
    @Column(nullable = false)
    private OrderStatus status;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItem> items = new ArrayList<>();

    @CreationTimestamp
    @Column(updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    private Instant updatedAt;

    // Static factory, not public constructor
    public static Order create(String customerEmail) {
        Order order = new Order();
        order.customerEmail = customerEmail;
        order.status = OrderStatus.PENDING;
        return order;
    }

    // Behavior on entity, not in service
    public void addItem(Product product, int quantity) {
        items.add(OrderItem.create(this, product, quantity));
    }
}
```

## Rules
- `@Enumerated(EnumType.STRING)` always — `ORDINAL` breaks on enum reordering
- `GenerationType.Long` for IDs — never expose auto-increment integers
- `@NoArgsConstructor(access = PROTECTED)` — required by JPA, hidden from app code
- `@Getter` from Lombok — no `@Setter` on entities (use behavior methods)
- Collections initialized inline (`= new ArrayList<>()`) — never null

## N+1 Prevention

**Identify:** One query for orders + N queries for each order's items = N+1.

**Fix with JOIN FETCH:**
```java
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.id = :id")
Optional<Order> findByIdWithItems(@Param("id") UUID id);

// For derived list queries — @EntityGraph instead of writing the JPQL
@EntityGraph(attributePaths = {"items", "items.product"})
List<Order> findByStatus(OrderStatus status);
```

Both fetch a collection in the same query, so **neither may be combined with `Pageable`** —
see "Paging an entity together with a collection" below.

**Fix with Projections for read-only views:**
```java
// Interface projection — no entity loaded
public interface OrderSummary {
    UUID getId();
    String getCustomerEmail();
    OrderStatus getStatus();
    Instant getCreatedAt();
}

List<OrderSummary> findByStatus(OrderStatus status); // fast, no lazy loading issues
```

## Query Patterns

```java
public interface OrderRepository extends JpaRepository<Order, UUID> {

    // Derived query — simple conditions
    List<Order> findByStatusAndCustomerEmail(OrderStatus status, String email);

    // JPQL — for joins and complex conditions
    @Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.status = :status")
    List<Order> findActiveOrdersWithItems(@Param("status") OrderStatus status);

    // Native SQL — only when JPQL can't do it
    @Query(value = "SELECT * FROM orders WHERE created_at > NOW() - INTERVAL '7 days'",
           nativeQuery = true)
    List<Order> findRecentOrders();

    // Exists check — faster than findById + isPresent
    boolean existsByCustomerEmailAndStatus(String email, OrderStatus status);

    // Projection
    List<OrderSummary> findByCustomerEmail(String email);
}
```

## Pagination

```java
// Always use Pageable for list endpoints
Page<Order> findByStatus(OrderStatus status, Pageable pageable);

// In service
Page<Order> orders = orderRepository.findByStatus(status, PageRequest.of(page, size, Sort.by("createdAt").descending()));
```

### Paging an entity together with a collection

`JOIN FETCH o.items` or `@EntityGraph(attributePaths = "items")` on a `Pageable` query does not
page in the database. One order with ten items is ten SQL rows, so Hibernate cannot apply
`OFFSET`/`FETCH` to orders: it loads **every matching order with all its items** and pages in
memory, logging only a warning (`HHH90003004: firstResult/maxResults specified with collection
fetch; applying in memory`, or with `hibernate.query.fail_on_pagination_over_collection_fetch=true`
an exception). Fine with 20 rows in test, an outage with thousands in production.

Page the parent first, then load the collection for that page only:

```java
// 1. page the IDs — paging works, no collection in this query
@Query(value = "SELECT o.id FROM Order o WHERE o.status = :status",
       countQuery = "SELECT COUNT(o) FROM Order o WHERE o.status = :status")
Page<UUID> findIdsByStatus(@Param("status") OrderStatus status, Pageable pageable);

// 2. fetch those orders with their items — no paging in this query
@EntityGraph(attributePaths = "items")
List<Order> findByIdIn(Collection<UUID> ids, Sort sort);
```

```java
Page<UUID> ids = orderRepository.findIdsByStatus(status, pageable);
List<Order> orders = orderRepository.findByIdIn(ids.getContent(), pageable.getSort());
return new PageImpl<>(orders, pageable, ids.getTotalElements());
```

Alternatives: keep the plain paged query and let `spring.jpa.properties.hibernate.default_batch_fetch_size: 100`
(or `@BatchSize(size = 100)` on the collection) load the items in `IN (...)` batches — one extra
query per page instead of one per order; or return a DTO projection when the endpoint is read-only.

## Bidirectional Relationships

```java
// Parent side (Order)
@OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
private List<OrderItem> items = new ArrayList<>();

// Child side (OrderItem) — owns the FK
@ManyToOne(fetch = FetchType.LAZY) // LAZY always on @ManyToOne
@JoinColumn(name = "order_id", nullable = false)
private Order order;

// Helper on parent to keep both sides in sync
public void addItem(OrderItem item) {
    items.add(item);
    item.setOrder(this);
}
```

## Deep Pagination — Keyset over OFFSET

`OFFSET` pagination scans and discards every skipped row. On page 5,000 the DB reads 100,000 rows to
return 20. For large or infinite-scroll datasets, paginate by the last seen key (the "seek" method):

```java
// ❌ Slow on deep pages — OFFSET grows linearly
Page<Order> findByStatus(OrderStatus status, Pageable pageable);

// ✅ Keyset — constant time regardless of depth. Pass the last row's createdAt + id.
@Query("""
    SELECT o FROM Order o
    WHERE o.status = :status
      AND (o.createdAt < :lastCreatedAt
           OR (o.createdAt = :lastCreatedAt AND o.id < :lastId))
    ORDER BY o.createdAt DESC, o.id DESC
    """)
List<Order> findNextPage(OrderStatus status, Instant lastCreatedAt, UUID lastId, Limit limit);
```

The `(createdAt, id)` tuple breaks ties so the cursor is stable when timestamps collide. Index `(status, created_at DESC, id DESC)`.

## Batch Inserts

Saving a list one row at a time is N round-trips. Enable JDBC batching so Hibernate groups them:

```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc.batch_size: 50
        order_inserts: true
        order_updates: true
```

Caveat: `GenerationType.IDENTITY` silently disables insert batching (Hibernate needs the generated key
per row). `GenerationType.UUID` or a pooled sequence preserves it — another reason to prefer UUIDs.

## Gotchas
- Agent uses `FetchType.EAGER` — always use `LAZY` on `@ManyToOne` and `@ManyToMany`
- Agent uses `@Enumerated(EnumType.ORDINAL)` — always use `STRING`
- Agent uses `Long` IDs — use `Long`
- Agent calls `findAll()` for list endpoints — always use `Pageable`
- Agent uses `OFFSET` pagination on huge tables — switch to keyset for deep pages
- Agent adds setters to entities — use behavior methods instead
- Agent forgets `orphanRemoval = true` on `@OneToMany` — child records become orphans
- Agent writes N+1 without realizing — check for `items` access in loops
- Agent "fixes" N+1 on a paged list with `JOIN FETCH`/`@EntityGraph` on the collection — Hibernate then pages in memory (HHH90003004); page the IDs first or use batch fetching
- Agent batches inserts with `GenerationType.IDENTITY` — batching is silently off; use `Long`/sequence
- Agent assumes Flyway comes transitively with `spring-boot-starter-data-jpa` — Boot's modular starters don't pull it in; add `spring-boot-starter-flyway` explicitly or migrations never run
- Agent imports `@EntityScan` from `org.springframework.boot.autoconfigure.domain` — it lives in `org.springframework.boot.persistence.autoconfigure`
- Agent uses `@MockBean`/`@SpyBean` in slice tests — removed; use `@MockitoBean`/`@MockitoSpyBean`, and add `spring-boot-starter-data-jpa-test` for `@DataJpaTest`
- Migrating from Boot 3: `spring.dao.exceptiontranslation.enabled` is now `spring.persistence.exceptiontranslation.enabled`