# Enforce the rule in CI

## Index

- [What can be enforced and what cannot](#what-can-be-enforced-and-what-cannot)
- [Python](#python)
- [TypeScript](#typescript)
- [Java](#java)
- [Go](#go)
- [Shared workflow](#shared-workflow)
- [Declared debt](#declared-debt)
- [Check that the rule bites](#check-that-the-rule-bites)

Base: principle 5 of the specification (Cockburn; Garrido de Paz, "Ports and Adapters Pattern"). The dependency direction is checked with the native tool of each language, not by manual review.

## What can be enforced and what cannot

| Rule | How it is enforced |
|---|---|
| The core does not import adapters | Import linter |
| The core does not import IO, framework or ORM | Import linter with a list of forbidden modules |
| Adapters do not import each other | Import linter by families or slices |
| The composition root is the only place that instantiates adapters | Heuristic audit and review; no import linter sees it |
| Ports are named by purpose | Audit and review |
| Every driven port has an in-memory double | Audit and review |
| Core tests do not start infrastructure | CI: run the test job without services |

Do not promise in the report more than the tool checks. A green linter means that imports comply; it does not mean that the architecture is right. (Specification, "Audit")

## Python

Tool: import-linter. Install it as a development dependency and copy `assets/python/importlinter.ini` to `.importlinter`.

```bash
pip install import-linter
cp "<skill-dir>/assets/python/importlinter.ini" .importlinter
lint-imports --config .importlinter
```

`<skill-dir>` is the directory that holds this skill's `SKILL.md`, the same path `SKILL.md` uses to run the audit.

The template has three contracts:

- `layers`: `app.adapters` above `app.core`. Adapters may import the core; the core may not import adapters.
- `forbidden` libraries: `app.core` may not import `sqlalchemy`, `psycopg2`, `pymongo`, `redis`, `requests`, `httpx`, `boto3`, `fastapi`, `flask` or `django`.
- `forbidden` between families: `app.adapters.driving` and `app.adapters.driven` do not import each other.

The layers contract treats `app.adapters` as a single layer, and the two family contracts only stop imports between the families. Imports between adapters of the same family are reported by the skill audit, not by this template. To check them in CI too, put each adapter in its own package and add an `independence` contract with one module per adapter.

Adapt `root_package` and the contract names to the repo. If the root package is not `app`, change it in the `[importlinter]` section and in every module of the contracts. External modules are watched with `include_external_packages = True`; without that option, import-linter only looks at internal imports.

`lint-imports` returns a non-zero code if a contract breaks. That is what makes the job fail.

## TypeScript

Tool: dependency-cruiser. Copy `assets/typescript/.dependency-cruiser.cjs` to the repo root.

Use the package manager the repo already uses (its lockfile says which: `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`); with no lockfile, use pnpm. Keep the repo's own TypeScript version.

```bash
pnpm add -D dependency-cruiser
pnpm exec depcruise src --config .dependency-cruiser.cjs
```

dependency-cruiser 18.7 needs TypeScript 6 or earlier. With TypeScript 7 it does not traverse modules, warns and exits with 0: a false green. Check that the output counts modules before trusting it, as the workflow does with its module count guard.

Template rules:

- `core-without-adapters`: `src/core` does not import `src/adapters`.
- `core-without-io`: `src/core` does not import `pg`, `express`, `fastify`, `axios`, `mysql2`, `mongoose`, `prisma`, `typeorm`, `@prisma/client`, `@aws-sdk` or the Node IO modules. An npm package resolves to its real file under `node_modules`, so the rule matches that path.
- `adapters-independent`: two families of `src/adapters` do not import each other, using the source path group.

Adjust the paths if the core is not in `src/core`. The independence rule can be refined one level further with the second path group, if each adapter lives in its own folder. Add the command to `package.json` so it also runs locally:

```json
"scripts": {
  "arch": "depcruise src --config .dependency-cruiser.cjs"
}
```

## Java

Tool: ArchUnit with JUnit 5. Add the test dependency `com.tngtech.archunit:archunit-junit5` and copy `assets/java/HexagonalArchitectureTest.java` to `src/test/java/com/example/app/`.

```bash
mvn test -Dtest=HexagonalArchitectureTest
```

With Gradle:

```bash
./gradlew test --tests '*HexagonalArchitectureTest'
```

Template rules:

- `..core..` does not depend on `..adapters..`.
- `..core..` does not depend on Spring, Jakarta, `java.sql`, `java.net.http`, Hibernate or the AWS, Google and Azure SDKs.
- The slices `adapters.(*)` do not depend on each other.

Adjust `@AnalyzeClasses(packages = ...)` to the root package. If the project already has an ArchUnit base class, reuse its import configuration instead of duplicating it.

## Go

Tool: go-arch-lint. Copy `assets/go/.go-arch-lint.yml` to the root.

```bash
go install github.com/fe3dback/go-arch-lint@latest
go-arch-lint check
```

Template components: `core`, `ports`, `adapters_driving`, `adapters_driven` and `cmd`. Dependencies are allow lists:

- `core` does not depend on anything in the project.
- `ports` depends on `core`.
- Adapters depend on `core` and `ports`.
- `cmd` depends on all of them and is the composition root.

The template sets `allow.deepScan: false` because the v3 AST linter confuses adapter injection into the core, done in the composition root, with a dependency from the core to the adapter. The import check stays active. It also sets `allow.depOnAnyVendor: true`: in v3 third party imports are denied by default, and `mayDependOn` only lists project components.

The price of `depOnAnyVendor: true` is that go-arch-lint lets any third-party import through from any component, so it does not enforce the vendor rule in Go. The Go forbidden list of the skill audit is the only vendor check there: `net/http`, `database/sql`, `gorm.io`, `github.com/aws`, `github.com/lib/pq`, `github.com/jackc/pgx`, `github.com/go-sql-driver/mysql`, `go.mongodb.org/mongo-driver`, `github.com/redis/go-redis`, `github.com/gin-gonic/gin`, `github.com/labstack/echo` and `github.com/gofiber/fiber`. Run the audit in CI as well.

Because these are allow lists, an adapter that imports another adapter fails without an extra rule. If you want to isolate each real adapter, declare one component per folder and leave its dependencies on `core` and `ports`.

The binary is installed in `$(go env GOPATH)/bin`. In CI, pin the version you use locally instead of `@latest`, and make sure that directory is in `PATH`. go-arch-lint 1.19 requires Go 1.25 or later, so the workflow pins Go 1.25 instead of reading `go.mod`, which may declare an earlier version.

## Shared workflow

Copy `assets/ci/architecture.yml` to `.github/workflows/architecture.yml`, uncomment the job for your language and delete the others. The workflow has `permissions: contents: read` and needs no secrets.

- One job per language, with its own `setup` and linter command.
- The job fails if the linter returns a non-zero code.
- If the repo has several languages, keep one job for each language with its own core.
- Mark the check as required in the main branch ruleset, if the repo uses rulesets.

The workflow as copied does not start: every job is commented out on purpose, so you enable only the one you need. A workflow with no active jobs does not run, so do not leave it like that on the main branch.

## Declared debt

If the repo already has violations and they cannot be fixed in the linter PR, do not turn the whole rule off. Declare the exception at the smallest point the tool allows, with a comment explaining why and an issue to remove it:

- dependency-cruiser: `pathNot` in the affected rule.
- ArchUnit: `@ArchIgnore` on the specific test, never on the whole class.
- import-linter: exclude the module from the contract and note the issue next to it.
- go-arch-lint: a separate component for legacy code, with looser dependencies.

An exception without an issue is invisible debt. The skill audit must count it as a finding and the report must say how many there are.

## Check that the rule bites

A badly configured linter always passes. Before considering the step done, check that it fails:

1. Create a temporary branch.
2. Add a forbidden import to a core file, for example `import sqlalchemy` or `import { Pool } from 'pg'`.
3. Run the linter command and confirm that it exits with an error and points at the file.
4. Undo the change and confirm that it goes green again.

If it does not fail, the rule is not looking where you think. Check the path, the root package or the module name before merging. This check is the only thing that separates an architecture contract from a CI ornament. (Specification, "Apply")
