# When to apply

## Index

- [Decision](#decision)
- [Real costs](#real-costs)
- [Partial adoption](#partial-adoption)
- [When not to apply](#when-not-to-apply)
- [How the decision is revisited](#how-the-decision-is-revisited)

Base: principle 9 of the specification (Cockburn and Garrido de Paz, "Hexagonal Architecture Explained"; AWS Prescriptive Guidance). The pattern is not free and the source says so before recommending it.

## Decision

Four signals decide: how long the project will live, how many actors drive it, how many external technologies there are and how much it hurts to change them. Do not add them up as points: when one signal sits at the opposite end, go down one level.

| Signal | Apply | Apply partially | Do not apply |
|---|---|---|---|
| Project lifetime | Years, with changing requirements | Medium term, bounded scope | Weeks or months, disposable |
| Actors that drive the app | Several (web, CLI, queues, tests, scripts) | Two, one of them tests | One only, always the same |
| External technologies | Several and replaceable (database, APIs, email) | One stable, with a test that replaces it | One fixed and not going to change |
| Criticality of the core | Business rules that matter and are tested | Some rules, little variation | CRUD or glue between services |
| Team and maintenance | Several people, handovers | One person with time | Nobody maintains it afterwards |
| Cost of changing an adapter | High or unknown | Low but not zero | Zero |

**Apply** when most rows fall to the left. **Do not apply** when most fall to the right. In between, **apply partially**.

When applying, the cheapest order is: composition root, in-memory doubles of the driven ports, driver ports for the use cases that will be tested, and finally splitting adapters. (Cockburn and Garrido de Paz)

## Real costs

| Cost | How it shows | When it is paid |
|---|---|---|
| Indirection | Every call crosses a port and an implementation; two places to read to follow a flow | Always |
| Mappings | Input DTO, entity, persistence model; code that converts between them | Whenever the shapes differ |
| More modules and files | One port and one adapter per boundary; longer builds and navigation | Always |
| Doubles to maintain | Every new driven port needs its in-memory double and its contract test | Always |
| Learning curve | Newcomers must know what they may touch and what they may not | When people join |
| Badly placed boundaries | Ports per technology or per table; the core ends up knowing the schema | If the name and purpose are not reviewed |

The cost is paid upfront and the benefit arrives when a technology changes or an actor is added. If that will not happen, the benefit never arrives. (AWS Prescriptive Guidance; Cockburn and Garrido de Paz)

Do not count as a cost of the pattern what the code already costs: validation, transactions and mapping exist with or without ports. What the pattern adds is where they live. (Garrido de Paz)

## Partial adoption

It works when the core matters but the repo does not justify full separation. Three pieces, in this order, without moving everything:

1. **Composition root**: a single place builds dependencies. Even if they are still concrete classes, `new` stops being scattered.
2. **In-memory doubles** of the external dependencies that tests touch today. With that, core tests stop needing a database.
3. **Driver port** for the use case that changes most, so it can be tested and called from two places.

What is left out: splitting every adapter, creating one port per service and reorganising folders. Add it when needed, not before. (Cockburn and Garrido de Paz)

A partial result is still hexagonal if the dependency direction holds at the boundaries that exist. You do not need all nine pieces to have the pattern. (Garrido de Paz)

## When not to apply

Do not apply it, and say so in the report, when two or more of these hold:

- The project is a script, a proof of concept or a single-use tool.
- There is one client and no other is expected.
- There is one stable external technology and replacing it is not planned.
- The core is CRUD without rules to test.
- Nobody will maintain the repo after delivery.

In that case the cost of indirection and mapping exceeds the cost of changing the code when needed. Migrating now is work with no return. (Cockburn and Garrido de Paz)

Two cheap measures are still worth it even here, because they add no ports:

- Do not import IO into business functions; pass it as an argument.
- Test those functions without starting infrastructure.

That leaves the door open to apply the pattern later without having paid for indirection too early. (Garrido de Paz)

## How the decision is revisited

The decision is not permanent. Look at the signals again when:

- A second actor appears (a CLI, a queue, a system test).
- Changing the database, the provider or the protocol is on the table.
- The core starts having slow tests because of infrastructure.
- The team grows and two people touch the same logic.

If none of these appears, do not migrate. If one appears and the rest still argue against it, apply partially. (Cockburn; AWS Prescriptive Guidance)

The cost of reverting a partial adoption is low: remove a port and call the concrete class again. The cost of reverting a half-finished full migration is high, because there are two live paths. That is why migration happens in steps with a stopping criterion, not all at once.
