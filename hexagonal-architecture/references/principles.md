# Principles

## Index

- [What it solves](#what-it-solves)
- [The nine principles](#the-nine-principles)
- [Glossary](#glossary)
- [Common misunderstandings](#common-misunderstandings)
- [Common mistakes](#common-mistakes)
- [Sources](#sources)

Each principle carries its source in parentheses. When two sources differ in emphasis, the one cited first wins. Principles come from tier 1 sources. Tier 2 adds practice. Tier 3 is used as worked examples and as a source of common mistakes, never as authority on the definition.

## What it solves

The pattern separates business logic from the devices and services around it, so the application can be driven and tested without them. Cockburn states it as an application that "can be driven equally well by users, programs, automated tests or scripts, and developed and tested in isolation from its runtime devices and databases". (Cockburn, "Hexagonal Architecture")

The goal is not to draw a hexagon. The goal is that the core does not know who calls it or whom it calls, and that this ignorance can be checked. (Cockburn; Garrido de Paz, "Ports and Adapters Pattern")

## The nine principles

### 1. One application, several ways to drive it

The application must be drivable by a person, another program, a test or a script, and testable in isolation from its external devices. The asymmetry that matters is inside/outside, not left/right: the drawing has no "input side" and "output side", it has a core and an exterior. (Cockburn; Garrido de Paz)

### 2. The hexagon is business logic without technology

Inside the hexagon lives the business: rules, entities, use cases. There are no references to frameworks, databases, HTTP, queues or files. (Cockburn; Cockburn and Garrido de Paz, "Hexagonal Architecture Explained")

"Without technology" does not mean "without code": the language, its pure standard library and utilities without IO are allowed. What does not enter is anything that forces infrastructure to be started in order to run the core. (Garrido de Paz)

### 3. Ports belong to the application

A port is the boundary the application offers or needs. There are two kinds:

- **Driver port** (or input port): the use case API that the outside can invoke.
- **Driven port** (or output port): the SPI the application needs from its environment.

Both are named by purpose, not by technology: `ForPlacingOrders`, not `PostgresPort` or `HttpPort`. (Cockburn; Garrido de Paz, "Ports and Adapters Pattern")

### 4. Adapters live outside

An adapter translates between the outside world and a port:

- **Driving adapter**: REST, CLI, a test, a queue consumer. It uses a driver port.
- **Driven adapter**: SQL, outgoing HTTP, email, files, an in-memory double. It implements a driven port.

A port supports several adapters at once. Adding one does not change the core. (Cockburn; Cockburn and Garrido de Paz)

### 5. Everything points inward

The core does not import adapters or IO or framework libraries. Adapters do not import each other. The dependency direction can be checked with a linter, not only by review. (Cockburn; Garrido de Paz)

The rule is about imports, not calls: at runtime the adapter calls the core, but at compile time the core does not know the adapter. That inversion is the pattern. (Garrido de Paz)

### 6. Configurable Dependency and composition root

Adapters are created in a single place: `main`, a bootstrap or the application container. That place injects them into the core. No other module instantiates a concrete adapter. (Cockburn, "Configurable Dependency"; Cockburn and Garrido de Paz)

"Configurable" means replaceable without touching the core: the same use case runs with SQL, with an in-memory double or with a remote API. The composition root is the only place that decides which one. (Garrido de Paz)

### 7. The pattern imposes neither layers nor DDD

Hexagonal does not require three layers, nor rich domain entities, nor aggregates, nor DDD-style repositories. "Domain, ports and adapters" as mandatory layers is a misunderstanding. The pattern only fixes a boundary and a dependency direction; inside the core, organise it as you wish. (Cockburn; Cockburn and Garrido de Paz)

DDD, clean architecture and onion can be combined with hexagonal, but they are not the same thing and are not included. (Garrido de Paz)

### 8. Four test levels

- **Core unit tests**: use cases and entities, without infrastructure.
- **Acceptance through driver ports**: the test enters through the same port as a real client and replaces driven ports with in-memory doubles.
- **Adapter integration**: the adapter against its real technology (database, HTTP server, queue).
- **System**: everything real, end to end.

One in-memory double per driven port is part of the architecture, not a test extra. (Cockburn; Cockburn and Garrido de Paz; Garrido de Paz)

### 9. When not to apply it

It does not pay off in a small, short-lived project with a single client and a single stable technology. Indirection, mappings and extra modules cost more than they save. In that case, the recommendation is not to migrate. (Cockburn and Garrido de Paz; AWS Prescriptive Guidance)

## Glossary

| Term | What it is | What it is not |
|---|---|---|
| **Driver** | The actor that starts the action: person, program, test, script. It "drives" the application. | It is not "the HTTP client". It can be a test. |
| **Driven** | The resource the application needs and does not control: database, API, email. It is "driven" by the application. | It is not "whatever goes over the network". A local file counts too. |
| **Port** | Stable boundary, named by purpose, owned by the application. | It is not an infrastructure class or a DTO. |
| **Driver port** | Use case API that the outside invokes. | It is not the REST controller. |
| **Driven port** | Interface the application needs from the outside. | It is not the concrete repository or the ORM. |
| **Adapter** | Translator between a port and a concrete technology. | It is not the place for business rules. |
| **Configurable Dependency** | Adapter replaceable without recompiling the core. | It does not require an injection framework. |
| **Composition root** | The only place that builds adapters and injects them. `main` is enough. | It is not another layer of the hexagon. |
| **In-memory double** | Implementation of a driven port for tests, without IO. | It is not a mock from the mocking framework of the day. |
| **Use case** | Core operation that implements a driver port. | It is not an application service with infrastructure dependencies. |

## Common misunderstandings

| Misunderstanding | What the source says |
|---|---|
| "Hexagonal means six layers or six sides with meaning" | The hexagon is a way of drawing; there are no six roles. What matters is inside/outside. (Cockburn) |
| "You need domain, ports and adapters as three layers" | The pattern imposes no internal layers. This is an explicit misunderstanding. (Cockburn and Garrido de Paz) |
| "Hexagonal, clean and onion are the same" | They share dependency inversion; clean and onion add layer rules that hexagonal does not require. (Garrido de Paz) |
| "One port per adapter" | One port, several adapters. The reverse multiplies interfaces for no reason. (Cockburn) |
| "Every internal service needs a port" | Only what crosses the boundary. Calling a pure core function needs no port. (Garrido de Paz) |
| "The core cannot have dependencies" | It cannot have outward or IO dependencies. Pure language utilities are fine. (Cockburn) |
| "The adapter only maps, it has no logic" | It can have format validation, retries, transactions and error translation. Business logic, no. (Garrido de Paz) |
| "You need an injection container" | `main` building dependencies and passing them in is a valid composition root. (Cockburn, "Configurable Dependency") |
| "Acceptance tests need the real database" | They enter through the driver port and use in-memory doubles of the driven ports. The database is tested in integration. (Cockburn and Garrido de Paz) |
| "Without DDD it is not hexagonal" | They are independent and combinable patterns. (Garrido de Paz) |

## Common mistakes

These come from tier 3 articles. They are useful as worked examples, but none of them defines the pattern. The audit detects some of them; where it does, the finding is noted.

| Mistake | Why it is wrong | Fix |
|---|---|---|
| Presenting the six-sided shape as the defining trait of the pattern | Tier 1 says the hexagon is only a drawing that leaves room for however many ports you need. The defining trait is the inside/outside boundary and the dependency direction, not the number of sides. | Drop the shape as a rule. Explain the pattern through ports, adapters and the dependency rule, and use any drawing that shows a core and an exterior. |
| Putting Spring `@Service` inside the domain | Tier 1, principle 2: the core has no framework references. The annotation couples the business class to the container and makes the core unreadable without Spring. | Move the annotation to a configuration class at the composition root, or wire the use case by hand in `main`. The core class stays a plain class. The audit reports framework imports in core as high. |
| Teaching a fixed three-layer recipe of domain, ports and adapters | Tier 1, principle 7: the pattern imposes no internal layers. "Domain, ports and adapters" as mandatory layers is an explicit misunderstanding. | Keep only the boundary and the dependency direction. Organise the core by use case, feature or whatever fits the domain, and say that the layout is a choice. |
| Listing REST controllers as inbound ports | Tier 1, principle 4: a controller is a driving adapter. A port belongs to the application and is named by purpose; the controller is a technology detail outside it. | Describe the controller as a driving adapter that calls a driver port. Keep the port in the core and let the controller translate HTTP into a port call. The audit reports controllers under a ports folder as medium. |
| Using `@Service` and `@Autowired` in the core | Tier 1, principles 2 and 6: the core must not depend on a framework, and adapters are injected from one composition root. Field injection hides the dependencies and defeats Configurable Dependency. | Use constructor injection with plain types, and let the composition root build the object graph. If a framework is unavoidable at the edge, keep it in the adapter or in the configuration class. |
| Persisting the domain `Product` directly through `JpaRepository<Product>`, so the ORM model and the domain model are the same class | Tier 1, principle 5: the core would import persistence and the dependency would point outward. It also removes the mapping that lets the domain and the schema evolve separately, and it makes the core untestable without the ORM. | Define a driven port for storage, implement it in a driven adapter with its own persistence model, and map between the two. Keep the domain class free of ORM annotations, and test the adapter against the real database in integration. |

## Sources

Tier 1 (definition):

- Cockburn, "Hexagonal Architecture": https://alistair.cockburn.us/hexagonal-architecture
- Garrido de Paz, "Hexagonal Architecture" (Ports and Adapters Pattern): https://jmgarridopaz.github.io/content/hexagonalarchitecture.html
- Cockburn and Garrido de Paz, "Hexagonal Architecture Explained" (book).

Tier 2 (practice):

- AWS Prescriptive Guidance, "Hexagonal architecture pattern": https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html
- Netflix Tech Blog, "Ready for changes with Hexagonal Architecture": https://netflixtechblog.com/ready-for-changes-with-hexagonal-architecture-b315ec967749
- Thoughtworks, Kinle Greshka, "Hexagonal Architecture Explained: A Practical Example": https://www.thoughtworks.com/insights/blog/architecture/hexagonal-architecture-explained-practical-example
- The Software House, Senecki and Goik, "Hexagonal Architecture": https://tsh.io/blog/hexagonal-architecture

Tier 3 (examples with flaws to call out):

- Filip Kisić, Comsysto Reply, "Hexagonal Architecture in Practice": https://medium.com/comsystoreply/hexagonal-architecture-in-practice-39a14b4bc807
- Dev Cookies, "A Detailed Guide to Hexagonal Architecture with Examples": https://devcookies.medium.com/a-detailed-guide-to-hexagonal-architecture-with-examples-042523acb1db

AWS describes the pattern with managed services and its benefits when replacing infrastructure. Netflix describes it at scale: the value is being able to change the data source and test the core without dragging infrastructure along. Thoughtworks shows a Spring Boot pizza shop and places domain and application inside the core; its DDD matrix for where a rule lives is useful, but it does not cover testing. The Software House uses Node and Express with a CQRS command bus, says that a simple CRUD probably does not justify the pattern, and accepts partial adoption with YAGNI and KISS. None of the tier 2 sources changes the principles above; they confirm them in different contexts. (AWS Prescriptive Guidance; Netflix Tech Blog; Thoughtworks; The Software House)
