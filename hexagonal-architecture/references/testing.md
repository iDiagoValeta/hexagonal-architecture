# Tests

## Index

- [The four levels](#the-four-levels)
- [Acceptance test through a driver port](#acceptance-test-through-a-driver-port)
- [Contract test for a driven port](#contract-test-for-a-driven-port)
- [Where each piece lives](#where-each-piece-lives)

Base: principle 8 of the specification (Cockburn; Cockburn and Garrido de Paz, "Hexagonal Architecture Explained"; Garrido de Paz, "Ports and Adapters Pattern"). The pattern holds because the core can be tested without infrastructure; if tests need the database to check a rule, the boundary is not in place.

## The four levels

| Level | Enters through | Replaces | What it proves | Speed |
|---|---|---|---|---|
| Core unit | Function or use case | Nothing, the core has no IO | Rules and calculations | Milliseconds |
| Acceptance | Driver port | Driven ports with in-memory doubles | The complete use case, with its orchestration | Milliseconds |
| Integration | Concrete adapter | Nothing: real or equivalent technology | Mapping, queries, schema, protocol | Seconds |
| System | Real driving adapter | Nothing | The end to end journey | Seconds or minutes |

Each level exists for a different reason. An acceptance test does not prove that the SQL query is right; an integration test does not prove that the business rule is correct. (Cockburn and Garrido de Paz)

**Core unit**: test the entity or the use case with trivial doubles or no dependencies. If you need to start a container, it is not a unit test.

**Acceptance**: enter through the same driver port as a real client and replace each driven port with its in-memory double. Test the orchestration of the use case, not the details of the adapter.

**Integration**: test the adapter against its technology. An in-memory SQLite works for SQL, an ephemeral server for HTTP, a container for PostgreSQL. What does not work is mocking the driver and calling that integration.

**System**: a real end to end journey, with the real adapters. Few, slow and fragile: use them for the critical path, not for every rule.

## Acceptance test through a driver port

The test enters through the driver port and checks the effect through an observable driven port. It does not inspect the internals of the use case or use generated mocks.

```python
# tests/acceptance/test_place_order.py
import unittest
from app.adapters.driven.in_memory_orders import InMemoryOrders
from app.core.place_order import PlaceOrder
from app.core.ports.for_placing_orders import ForPlacingOrders

class PlaceOrderAcceptance(unittest.TestCase):
    def setUp(self) -> None:
        self.orders = InMemoryOrders()
        self.app: ForPlacingOrders = PlaceOrder(self.orders)

    def test_registers_the_order_and_leaves_it_queryable(self) -> None:
        order = self.app.place("ana", 1999)
        self.assertEqual(self.orders.by_id(order.id), order)

    def test_two_orders_do_not_overwrite_each_other(self) -> None:
        first = self.app.place("ana", 1999)
        second = self.app.place("luis", 500)
        self.assertEqual(self.orders.by_id(first.id), first)
        self.assertEqual(self.orders.by_id(second.id), second)
```

What makes the test useful:

- The `app` variable is typed as `ForPlacingOrders`, so the test cannot call methods that are not part of the port.
- The double is real, in memory and observable: it checks the stored state, not a call.
- There is no module patching or framework `Mock`. If the use case needs a complex mock, the dependency is badly cut.
- The test survives changing SQLite for PostgreSQL: it does not touch the real adapter.

In TypeScript and Java the same test is written against the driver port interface and an instance of `InMemoryOrders`. In Go, against `ports.ForPlacingOrders` and `driven.NewInMemoryOrders()`. The language changes; the shape does not.

## Contract test for a driven port

An in-memory double is only useful if it behaves like the real adapter in what the port promises. Write a contract suite and run it against both:

```python
# tests/contracts/test_for_storing_orders.py
import unittest
from app.adapters.driven.in_memory_orders import InMemoryOrders
from app.adapters.driven.sqlite_orders import SqliteOrders
from app.core.order import Order

class ContractForStoringOrders:
    def make(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def test_saves_and_retrieves(self) -> None:
        port = self.make()
        order = Order("1", "ana", 1999)
        port.save(order)
        self.assertEqual(port.by_id("1"), order)

    def test_returns_none_when_missing(self) -> None:
        self.assertIsNone(self.make().by_id("nobody"))

class TestInMemory(ContractForStoringOrders, unittest.TestCase):
    def make(self):  # type: ignore[no-untyped-def]
        return InMemoryOrders()

class TestSqlite(ContractForStoringOrders, unittest.TestCase):
    def make(self):  # type: ignore[no-untyped-def]
        return SqliteOrders(":memory:")
```

The contract belongs to the port, not to the adapter. If a real adapter cannot satisfy it, either the port is badly defined or the adapter is not an adapter for that port.

When the real adapter needs infrastructure (PostgreSQL, a broker), the contract runs in the integration job with the real technology and the double runs in the test job. Both must pass.

## Where each piece lives

- **In-memory double**: in `tests/doubles/` or in `adapters/driven/`, in a single place. One double per driven port. If there are two copies, the audit cannot tell which one is the good one.
- **Acceptance test**: `tests/acceptance/`, at least one per driver port.
- **Contract test**: `tests/contracts/`, one per driven port.
- **Integration test**: next to the adapter or in `tests/integration/`, one per real adapter.
- **System test**: `tests/system/`, the critical path.
- **Test discovery**: a `tests/` folder with `test_*.py` but no `__init__.py` and no pytest config makes `python3 -m unittest` import nothing and run zero tests silently; add `tests/__init__.py` or configure pytest.

The audit looks for an in-memory double per driven port in tests. If the double lives inside the production adapter it still counts, but do not put it in the deployed artifact if it is not needed.

## What not to do

| Practice | Why it fails |
|---|---|
| Mocking the driven port with the mocking framework in the acceptance test | It checks calls, not behaviour; the test stays green if the use case stops saving. |
| Using the real database in the acceptance test | It turns a rule test into an infrastructure test and makes it slow and fragile. |
| Testing the adapter with the port mocked | It does not test SQL, mapping or driver errors; it only tests that the class exists. |
| Inspecting private attributes of the use case | It couples the test to the implementation and blocks the refactor that the migration needs. |
| One giant system test for everything | It is slow, fails for unrelated reasons and does not say which rule broke. |
| Skipping the contract test for the double | The double and the real adapter diverge and acceptance lies. |
| Testing the entity through the controller | It mixes levels; the failure appears far from its cause. |

The criterion for choosing a level: if the failure you fear is in a rule, test the core or the driver port. If it is in the translation to the technology, test the adapter. If it is in the wiring, test the system. (Cockburn and Garrido de Paz)
