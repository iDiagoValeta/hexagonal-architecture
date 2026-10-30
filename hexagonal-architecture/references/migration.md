# Incremental migration

## Index

- [Golden rule](#golden-rule)
- [Before touching code](#before-touching-code)
- [The steps](#the-steps)
- [Re-audit](#re-audit)
- [Signals to stop](#signals-to-stop)
- [PR checklist](#pr-checklist)

Base: principles 5, 6 and 8 of the specification, and the "Apply" section (Cockburn and Garrido de Paz, "Hexagonal Architecture Explained"; Cockburn, "Configurable Dependency"). Migration is a strangler: the old code stays alive until the new code replaces it, and is removed afterwards.

## Golden rule

One use case or one adapter per PR. Never a big bang. If the PR touches two use cases, split the PR. (Specification, "Apply"; Cockburn and Garrido de Paz)

Each step leaves the repo working and with fewer high findings, or the same. If they increase, the step is wrong and is reverted before continuing.

## Before touching code

1. **Audit and save the baseline.** Run the audit and count findings by severity:

   ```bash
   python3 "<skill-dir>/scripts/audit.py" --path . --json > /tmp/hexagonal-before.json
   ```

   `<skill-dir>` is the directory that holds this skill's `SKILL.md`, the same path `SKILL.md` uses to run the audit. The JSON goes outside the repo or into the issue, not as a versioned file.

2. **Write `.hexagonal.json`.** Set `core`, `ports`, `driving_adapters`, `driven_adapters`, `composition_root` and `forbidden_in_core` to the real paths. Without it, the audit infers by name and says so; inference is good enough to start, not to finish.

3. **Take inventory.** List the use cases, the actors that drive them and every external dependency (database, API, email, files, queue). One use case per line, with its current adapter.

4. **Agree the stopping criterion** with the repo maintainer: what is migrated, what stays as it is and what counts as done. Without agreement, the work has no end.

5. **Open branch and issue** following `github-practices` if it is installed: `refactoring/<issue>-<context>`, draft PR. If it is not installed, use the same format.

## The steps

### Step 0. Freeze behaviour

Before moving anything, the tests covering the use case must exist and pass. If there are no tests, the first PR adds them against the current code, without refactoring.

**Done when**: the use case has passing tests and the inventory is in the issue.

If the case has no tests and they cannot be written without rewriting it, that is the finding: stop and decide whether the case belongs in the migration.

### Step 1. Extract the driven port and its in-memory double

Create the interface named by purpose, make the use case depend on it and write the in-memory double. Add a contract test that runs against the double and against the real adapter.

**Done when**:

- The use case compiles without importing the IO library or the driver.
- The in-memory double implements the port and passes the contract test.
- The real adapter still passes its integration test.
- The audit has not increased the number of high findings.

Do not change the technology or move files yet. This PR only inverts the dependency.

### Step 2. Move the use case into the core

Move the file to the core package, fix imports and create the driver port if the case is invoked from outside. The core must not end up importing the controller, the repository or the framework.

**Done when**:

- The core only imports the language, pure utilities and its own ports.
- The driver port exists and the use case implements it.
- The use case tests run without infrastructure.
- The old path disappears or stays as a facade that delegates; there are not two copies of the logic.

### Step 3. Put the real adapter behind the port

Wrap the existing persistence or API code in a class that implements the driven port. Do not rewrite the data access logic in this step: wrap, do not reinvent.

**Done when**:

- The adapter implements the port and its integration test passes.
- Nobody outside the composition root imports the concrete class.
- The use case does not know the schema, the table or the HTTP client.

### Step 4. Move the driving adapter

Make the controller, the CLI or the queue consumer call the driver port, not the concrete service. Input DTO mapping and error translation live in the adapter.

**Done when**:

- The driving adapter imports the driver port and the types of its boundary, nothing from the core internals or from other adapters.
- The acceptance test enters through the driver port with in-memory doubles.
- The endpoint or command responds as before.

### Step 5. A single composition root

Gather adapter construction in `main`, bootstrap or container. Remove scattered factories, singletons and `new`.

**Done when**:

- Searching for adapter instantiations outside the composition root returns nothing, or only cases justified in the issue.
- Changing one adapter for another happens in one place.
- The audit reduces the medium findings about instantiation.

### Step 6. Fix the rule in CI

Copy the template from `assets/` for the language and enable a job. Check that the linter fails with a deliberate violation and passes without it.

**Done when**:

- CI red with a forbidden import injected in a test branch.
- CI green with the correct code.
- The workflow uses `contents: read` and needs no secrets.

Steps 1 to 4 are repeated for each use case. Step 5 is done once per application and step 6 once per repo. Do not mix two use cases in the same PR even if they are similar. (Specification, "Apply")

### While both paths coexist

- The old code is still what runs in production until the new code is tested. The strangler does not switch off the old path early.
- If there is a facade, let it delegate in one place; two copies of the business rule are worse than not migrating.
- The old path tests stay until it is removed. Do not delete them in the PR that introduces the new path.
- Removing the old code is a separate PR, with its own verification.

## Re-audit

After each PR:

```bash
python3 "<skill-dir>/scripts/audit.py" --path . --json > /tmp/hexagonal-after.json
```

Compare by severity and by area. The total is not enough: one new high finding offset by two resolved medium ones is still a regression. Also look at findings by file to confirm that the change moved what you thought.

If the number of high findings increases, the PR is not merged. It is fixed or reverted. (Specification, "Apply")

The audit is static and heuristic. A zero does not prove that the architecture is right: it proves that the violations the script knows how to look for are not visible. Acceptance tests and review of the composition root cover what the script does not see. (Specification, "Audit")

## Signals to stop

Stop the current step, revert the PR and record the reason. Do not keep accumulating changes waiting for the next one to fix them.

- Two consecutive steps without reducing the high findings or keeping them level.
- The port starts having technology names or types (`PostgresPort`, `ResultSet`, the ORM `Document`).
- The in-memory double cannot reproduce the behaviour and the solution is to mock the ORM.
- The use case needs more dependencies than it had, a sign that the port groups things that do not belong together.
- Behaviour changes appear that the tests do not cover.
- The repository fits "do not apply" in `when-to-apply.md` and the migration no longer has a clear return.
- The team cannot maintain both paths for longer than agreed.

Stopping is not failing: it leaves the repo in the last healthy state and documents where it stopped. The next attempt starts from there, not from zero.

## PR checklist

```markdown
- [ ] One use case or one adapter only
- [ ] The core adds no IO, framework or adapter imports
- [ ] The driven port and its in-memory double are up to date
- [ ] Unit and acceptance tests are green
- [ ] The adapter integration test is green
- [ ] The audit does not increase high findings
- [ ] No observable behaviour changes
- [ ] The composition root is still the only place that instantiates adapters
```
