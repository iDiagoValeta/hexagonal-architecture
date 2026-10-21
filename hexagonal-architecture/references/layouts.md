# Reference layouts

## Index

- [How to read this](#how-to-read-this)
- [Python](#python)
- [TypeScript](#typescript)
- [Java](#java)
- [Go](#go)
- [Shared rules](#shared-rules)

## How to read this

Each language shows the same use case: place an order and store it. There are eight pieces: entity, driver port, driven port, use case, real driven adapter, in-memory double, driving adapter and composition root.

The paths are a proposal, not a standard. What cannot move is the dependency direction: the core does not import adapters and adapters do not import each other. (Cockburn; Garrido de Paz, "Ports and Adapters Pattern")

In the examples, `ports` lives inside the core because a port belongs to the application. If the repo already has a separate `src/ports`, that works too as long as the core imports it and not the other way round.

## Python

Tree:

```
app/
  core/
    order.py
    place_order.py
    ports/
      for_placing_orders.py
      for_storing_orders.py
  adapters/
    driving/http.py
    driven/sqlite_orders.py
    driven/in_memory_orders.py
  main.py
```

Add `__init__.py` in every folder; they are omitted from the tree and the code.

```python
# app/core/order.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Order:
    id: str
    customer: str
    total_cents: int
```

```python
# app/core/ports/for_placing_orders.py
from typing import Protocol
from app.core.order import Order

class ForPlacingOrders(Protocol):
    def place(self, customer: str, total_cents: int) -> Order: ...
```

```python
# app/core/ports/for_storing_orders.py
from typing import Protocol
from app.core.order import Order

class ForStoringOrders(Protocol):
    def save(self, order: Order) -> None: ...
    def by_id(self, order_id: str) -> Order | None: ...
```

```python
# app/core/place_order.py
import uuid
from app.core.order import Order
from app.core.ports.for_storing_orders import ForStoringOrders

class PlaceOrder:
    def __init__(self, orders: ForStoringOrders) -> None:
        self._orders = orders

    def place(self, customer: str, total_cents: int) -> Order:
        order = Order(id=str(uuid.uuid4()), customer=customer, total_cents=total_cents)
        self._orders.save(order)
        return order
```

```python
# app/adapters/driven/sqlite_orders.py
import sqlite3
from app.core.order import Order
from app.core.ports.for_storing_orders import ForStoringOrders

class SqliteOrders(ForStoringOrders):
    def __init__(self, path: str) -> None:
        self._db = sqlite3.connect(path)
        self._db.execute(
            "create table if not exists orders "
            "(id text primary key, customer text, total_cents integer)"
        )

    def save(self, order: Order) -> None:
        with self._db:
            self._db.execute(
                "insert into orders values (?, ?, ?)",
                (order.id, order.customer, order.total_cents),
            )

    def by_id(self, order_id: str) -> Order | None:
        row = self._db.execute(
            "select id, customer, total_cents from orders where id = ?", (order_id,)
        ).fetchone()
        return Order(*row) if row else None
```

```python
# app/adapters/driven/in_memory_orders.py
from app.core.order import Order
from app.core.ports.for_storing_orders import ForStoringOrders

class InMemoryOrders(ForStoringOrders):
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        self._orders[order.id] = order

    def by_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
```

```python
# app/adapters/driving/http.py
import json
from http.server import BaseHTTPRequestHandler
from app.core.ports.for_placing_orders import ForPlacingOrders

def handler(app: ForPlacingOrders) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            order = app.place(body["customer"], body["total_cents"])
            payload = json.dumps(order.__dict__).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return Handler
```

```python
# app/main.py
from http.server import HTTPServer
from app.adapters.driven.sqlite_orders import SqliteOrders
from app.adapters.driving.http import handler
from app.core.place_order import PlaceOrder

def main() -> None:
    app = PlaceOrder(SqliteOrders("orders.db"))
    HTTPServer(("127.0.0.1", 8000), handler(app)).serve_forever()

if __name__ == "__main__":
    main()
```

## TypeScript

Tree:

```
src/
  core/
    order.ts
    place-order.ts
    ports/
      for-placing-orders.ts
      for-storing-orders.ts
  adapters/
    driving/http-server.ts
    driven/postgres-orders.ts
    driven/in-memory-orders.ts
  main.ts
```

```ts
// src/core/order.ts
export interface Order {
  id: string;
  customer: string;
  totalCents: number;
}
```

```ts
// src/core/ports/for-placing-orders.ts
import type { Order } from '../order';

export interface ForPlacingOrders {
  place(customer: string, totalCents: number): Promise<Order>;
}
```

```ts
// src/core/ports/for-storing-orders.ts
import type { Order } from '../order';

export interface ForStoringOrders {
  save(order: Order): Promise<void>;
  findById(id: string): Promise<Order | null>;
}
```

```ts
// src/core/place-order.ts
import { randomUUID } from 'node:crypto';
import type { Order } from './order';
import type { ForPlacingOrders } from './ports/for-placing-orders';
import type { ForStoringOrders } from './ports/for-storing-orders';

export class PlaceOrder implements ForPlacingOrders {
  constructor(private readonly orders: ForStoringOrders) {}

  async place(customer: string, totalCents: number): Promise<Order> {
    const order: Order = { id: randomUUID(), customer, totalCents };
    await this.orders.save(order);
    return order;
  }
}
```

```ts
// src/adapters/driven/postgres-orders.ts
import type { Pool } from 'pg';
import type { Order } from '../../core/order';
import type { ForStoringOrders } from '../../core/ports/for-storing-orders';

export class PostgresOrders implements ForStoringOrders {
  constructor(private readonly pool: Pool) {}

  async save(order: Order): Promise<void> {
    await this.pool.query(
      'insert into orders (id, customer, total_cents) values ($1, $2, $3)',
      [order.id, order.customer, order.totalCents],
    );
  }

  async findById(id: string): Promise<Order | null> {
    const { rows } = await this.pool.query(
      'select id, customer, total_cents from orders where id = $1',
      [id],
    );
    const row = rows[0];
    return row
      ? { id: row.id, customer: row.customer, totalCents: row.total_cents }
      : null;
  }
}
```

```ts
// src/adapters/driven/in-memory-orders.ts
import type { Order } from '../../core/order';
import type { ForStoringOrders } from '../../core/ports/for-storing-orders';

export class InMemoryOrders implements ForStoringOrders {
  private readonly orders = new Map<string, Order>();

  async save(order: Order): Promise<void> {
    this.orders.set(order.id, order);
  }

  async findById(id: string): Promise<Order | null> {
    return this.orders.get(id) ?? null;
  }
}
```

```ts
// src/adapters/driving/http-server.ts
import { createServer, type Server } from 'node:http';
import type { ForPlacingOrders } from '../../core/ports/for-placing-orders';

export function createHttpServer(app: ForPlacingOrders): Server {
  return createServer(async (req, res) => {
    if (req.method !== 'POST' || req.url !== '/orders') {
      res.writeHead(404).end();
      return;
    }
    const chunks: Buffer[] = [];
    for await (const chunk of req) chunks.push(chunk as Buffer);
    const body = JSON.parse(Buffer.concat(chunks).toString());
    const order = await app.place(body.customer, body.totalCents);
    res.writeHead(201, { 'Content-Type': 'application/json' }).end(JSON.stringify(order));
  });
}
```

```ts
// src/main.ts
import { Pool } from 'pg';
import { PostgresOrders } from './adapters/driven/postgres-orders';
import { createHttpServer } from './adapters/driving/http-server';
import { PlaceOrder } from './core/place-order';

const app = new PlaceOrder(new PostgresOrders(new Pool({
  connectionString: process.env.DATABASE_URL,
})));
createHttpServer(app).listen(3000);
```

## Java

Tree:

```
src/main/java/com/example/app/
  core/
    Order.java
    PlaceOrder.java
    ports/
      ForPlacingOrders.java
      ForStoringOrders.java
  adapters/
    driving/OrderController.java
    driven/JdbcOrders.java
    driven/InMemoryOrders.java
  Application.java
```

```java
// core/Order.java
package com.example.app.core;

public record Order(String id, String customer, long totalCents) {}
```

```java
// core/ports/ForPlacingOrders.java
package com.example.app.core.ports;

import com.example.app.core.Order;

public interface ForPlacingOrders {
    Order place(String customer, long totalCents);
}
```

```java
// core/ports/ForStoringOrders.java
package com.example.app.core.ports;

import com.example.app.core.Order;
import java.util.Optional;

public interface ForStoringOrders {
    void save(Order order);
    Optional<Order> findById(String id);
}
```

```java
// core/PlaceOrder.java
package com.example.app.core;

import com.example.app.core.ports.ForPlacingOrders;
import com.example.app.core.ports.ForStoringOrders;
import java.util.UUID;

public final class PlaceOrder implements ForPlacingOrders {
    private final ForStoringOrders orders;

    public PlaceOrder(ForStoringOrders orders) {
        this.orders = orders;
    }

    @Override
    public Order place(String customer, long totalCents) {
        Order order = new Order(UUID.randomUUID().toString(), customer, totalCents);
        orders.save(order);
        return order;
    }
}
```

```java
// adapters/driven/JdbcOrders.java
package com.example.app.adapters.driven;

import com.example.app.core.Order;
import com.example.app.core.ports.ForStoringOrders;
import java.sql.*;
import java.util.Optional;
import javax.sql.DataSource;

public final class JdbcOrders implements ForStoringOrders {
    private final DataSource dataSource;

    public JdbcOrders(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void save(Order order) {
        String sql = "insert into orders (id, customer, total_cents) values (?, ?, ?)";
        try (Connection c = dataSource.getConnection();
             PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, order.id());
            ps.setString(2, order.customer());
            ps.setLong(3, order.totalCents());
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }

    @Override
    public Optional<Order> findById(String id) {
        String sql = "select id, customer, total_cents from orders where id = ?";
        try (Connection c = dataSource.getConnection();
             PreparedStatement ps = c.prepareStatement(sql)) {
            ps.setString(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next()
                    ? Optional.of(new Order(rs.getString(1), rs.getString(2), rs.getLong(3)))
                    : Optional.empty();
            }
        } catch (SQLException e) {
            throw new IllegalStateException(e);
        }
    }
}
```

```java
// adapters/driven/InMemoryOrders.java
package com.example.app.adapters.driven;

import com.example.app.core.Order;
import com.example.app.core.ports.ForStoringOrders;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

public final class InMemoryOrders implements ForStoringOrders {
    private final Map<String, Order> orders = new HashMap<>();

    @Override
    public void save(Order order) {
        orders.put(order.id(), order);
    }

    @Override
    public Optional<Order> findById(String id) {
        return Optional.ofNullable(orders.get(id));
    }
}
```

```java
// adapters/driving/OrderController.java
package com.example.app.adapters.driving;

import com.example.app.core.Order;
import com.example.app.core.ports.ForPlacingOrders;
import org.springframework.web.bind.annotation.*;

@RestController
public final class OrderController {
    private final ForPlacingOrders orders;

    public OrderController(ForPlacingOrders orders) {
        this.orders = orders;
    }

    @PostMapping("/orders")
    public Order place(@RequestBody PlaceOrderRequest request) {
        return orders.place(request.customer(), request.totalCents());
    }

    public record PlaceOrderRequest(String customer, long totalCents) {}
}
```

```java
// Application.java
package com.example.app;

import com.example.app.adapters.driven.JdbcOrders;
import com.example.app.core.PlaceOrder;
import com.example.app.core.ports.ForPlacingOrders;
import com.example.app.core.ports.ForStoringOrders;
import javax.sql.DataSource;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class Application {
    @Bean
    ForStoringOrders forStoringOrders(DataSource dataSource) {
        return new JdbcOrders(dataSource);
    }

    @Bean
    ForPlacingOrders forPlacingOrders(ForStoringOrders orders) {
        return new PlaceOrder(orders);
    }
}
```

In Spring the container is the composition root: `Application` declares the adapters and the core does not import them.

## Go

Tree:

```
cmd/api/main.go
internal/
  core/
    order.go
    ports.go
    place_order.go
  ports/
    for_placing_orders.go
  adapters/
    driving/http.go
    driven/sql_orders.go
    driven/in_memory_orders.go
```

The driven port is declared in `core` because it is the interface the use case consumes. If it lived in `ports`, `core` would have to import it and `ports` imports `core` for the entity: a cycle. The driver port does live in `ports`.

```go
// internal/core/order.go
package core

type Order struct {
	ID         string
	Customer   string
	TotalCents int64
}
```

```go
// internal/core/ports.go
package core

type ForStoringOrders interface {
	Save(order Order) error
	FindByID(id string) (Order, bool, error)
}
```

```go
// internal/ports/for_placing_orders.go
package ports

import "example.com/app/internal/core"

type ForPlacingOrders interface {
	Place(customer string, totalCents int64) (core.Order, error)
}
```

```go
// internal/core/place_order.go
package core

import (
	"crypto/rand"
	"encoding/hex"
)

type PlaceOrder struct {
	orders ForStoringOrders
}

func NewPlaceOrder(orders ForStoringOrders) *PlaceOrder {
	return &PlaceOrder{orders: orders}
}

func (p *PlaceOrder) Place(customer string, totalCents int64) (Order, error) {
	order := Order{ID: newID(), Customer: customer, TotalCents: totalCents}
	if err := p.orders.Save(order); err != nil {
		return Order{}, err
	}
	return order, nil
}

func newID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}
```

```go
// internal/adapters/driven/sql_orders.go
package driven

import (
	"database/sql"
	"errors"

	"example.com/app/internal/core"
)

type SQLOrders struct {
	db *sql.DB
}

func NewSQLOrders(db *sql.DB) *SQLOrders {
	return &SQLOrders{db: db}
}

func (a *SQLOrders) Save(order core.Order) error {
	_, err := a.db.Exec(
		"insert into orders (id, customer, total_cents) values ($1, $2, $3)",
		order.ID, order.Customer, order.TotalCents,
	)
	return err
}

func (a *SQLOrders) FindByID(id string) (core.Order, bool, error) {
	var order core.Order
	err := a.db.QueryRow(
		"select id, customer, total_cents from orders where id = $1", id,
	).Scan(&order.ID, &order.Customer, &order.TotalCents)
	if errors.Is(err, sql.ErrNoRows) {
		return core.Order{}, false, nil
	}
	return order, err == nil, err
}
```

```go
// internal/adapters/driven/in_memory_orders.go
package driven

import (
	"sync"

	"example.com/app/internal/core"
)

type InMemoryOrders struct {
	mu     sync.Mutex
	orders map[string]core.Order
}

func NewInMemoryOrders() *InMemoryOrders {
	return &InMemoryOrders{orders: map[string]core.Order{}}
}

func (m *InMemoryOrders) Save(order core.Order) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.orders[order.ID] = order
	return nil
}

func (m *InMemoryOrders) FindByID(id string) (core.Order, bool, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	order, ok := m.orders[id]
	return order, ok, nil
}
```

```go
// internal/adapters/driving/http.go
package driving

import (
	"encoding/json"
	"net/http"

	"example.com/app/internal/ports"
)

func NewHandler(app ports.ForPlacingOrders) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /orders", func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Customer   string `json:"customer"`
			TotalCents int64  `json:"totalCents"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		order, err := app.Place(body.Customer, body.TotalCents)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusCreated)
		_ = json.NewEncoder(w).Encode(order)
	})
	return mux
}
```

```go
// cmd/api/main.go
package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"

	_ "github.com/lib/pq"

	"example.com/app/internal/adapters/driven"
	"example.com/app/internal/adapters/driving"
	"example.com/app/internal/core"
)

func main() {
	db, err := sql.Open("postgres", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal(err)
	}
	app := core.NewPlaceOrder(driven.NewSQLOrders(db))
	log.Fatal(http.ListenAndServe(":8080", driving.NewHandler(app)))
}
```

## Shared rules

- The port is named by purpose and stays stable; the adapter changes technology without touching it. (Cockburn; Garrido de Paz)
- One port can have several adapters, and an adapter implements a single port. If an adapter implements two, they are probably two adapters.
- The composition root is the only place that imports concrete adapters. If another module does, the finding is medium severity in the audit.
- Adapters can have technical logic: mapping, transactions, retries, error translation. Business logic, no.
- Do not share models between layers for convenience. If the API DTO and the entity match today, mapping is trivial today and necessary the day they stop matching.
- The examples above return the core entity straight from the driving adapter to stay short. In production the driving adapter maps to its own transport DTO at the boundary; the audit does not check that mapping.
