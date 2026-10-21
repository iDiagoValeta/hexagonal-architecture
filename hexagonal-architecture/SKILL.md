---
name: hexagonal-architecture
description: Audits a repository against hexagonal architecture (ports and adapters) and applies only the changes the user approves. It finds core code that imports adapters, frameworks or IO libraries, adapters that import each other, adapter instantiation outside the composition root, technology names in ports and missing in-memory doubles, then proposes a migration in small steps plus a CI contract. Use when asked about hexagonal architecture, ports and adapters, driving or driven ports, domain isolation, dependency injection, composition root, clean architecture or DDD, or when auditing or refactoring a repo toward a technology-free core.
license: MIT
metadata:
  opencode/slash: "true"
---

# hexagonal-architecture

Audits a repo and applies only what is approved. The pattern is not free: when the repo does not justify it, the skill says so and recommends not migrating.

**Mandatory gate before any write to the repo or GitHub** (creating or editing files, `git commit`, `git push`, `gh pr`, or any command that changes state): the request must carry a written OK for THAT specific change, for example "apply the config", "open the PR", "I approve all the changes". Asking for the goal ("migrate this repo to hexagonal") is NOT that OK. Without it, your reply ends with the exact diff or command, how to undo it, and the question "shall I apply it?", even if nobody is there to answer. In a non-interactive run, deliver the plan and stop. For agents that support permission rules, the block in [assets/agent-permissions/](assets/agent-permissions/) asks before `git commit`, `git push` and `gh pr`, which is history and remote; it does not gate file edits, which remain gated by the instruction above.

## When to use it

- Asked to audit or refactor a repo toward hexagonal architecture, ports and adapters, or a technology-free core.
- The domain imports an ORM, a framework, an HTTP client or a database driver.
- A use case cannot be tested without infrastructure.
- Adapters are instantiated all over the codebase instead of in one composition root.
- A CI contract is needed to keep the dependency direction from regressing.
- A migration plan is needed for a legacy repo without a big bang.

## When not to use it

Recommend against migrating, and say why in the report, when the project is small, short-lived, has a single client and a single stable technology, or its core is CRUD without rules to test. The full decision table and the partial option are in [references/when-to-apply.md](references/when-to-apply.md). Do not apply the pattern to code nobody will maintain.

## Flow

Copyable checklist:

```markdown
- [ ] Audit the repo in read-only mode
- [ ] Report findings by severity: high, medium, low, info
- [ ] Decide apply, partial or skip, with reasons
- [ ] Propose .hexagonal.json for the real paths
- [ ] Add the CI contract for the repo language
- [ ] Migrate one use case or one adapter per PR
- [ ] Re-audit and confirm high findings never increase
```

### 1. Audit

Run the audit script, do not read it:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/audit.py" --path . --json
```

In Claude Code the path is `${CLAUDE_SKILL_DIR}/scripts/audit.py`. In other agents, use the path of the directory where this skill is installed. Flags: `--path` for the repo root, `--config` for an explicit config file, `--json` for machine-readable output. The audit is read-only and changes nothing.

Without `.hexagonal.json` the script infers roles from folder names and says so in the report. Inference is a starting point, not a verdict.

### 2. Report

Sort findings by severity and state what could not be checked.

- **High**: the dependency rule is broken. Core imports an adapter, an ORM, a framework, an HTTP client or a database driver.
- **Medium**: the structure leaks. An adapter imports another adapter, an adapter is instantiated outside the composition root, a controller sits under a ports folder, a driven port has no in-memory double in tests, or the core has no tests isolated from infrastructure.
- **Low**: naming and hygiene. A port is named after a technology, or a Python `tests/` folder has no `__init__.py` and no pytest config, so `python3 -m unittest` discovers nothing.
- **Info**: not enough evidence. The structure could not be detected.

A green audit does not prove the architecture is right: it proves that the script did not see the violations it knows how to look for. Say so.

### 3. Decide

Choose one outcome and justify it with the signals in [references/when-to-apply.md](references/when-to-apply.md):

- **Apply**: several actors, several replaceable technologies, a core with rules worth testing.
- **Partial**: one or two signals, with a bounded scope. Composition root, in-memory doubles, one driver port.
- **Skip**: small, short-lived, single client, single stable technology, CRUD. Recommend not migrating and stop.

### 4. Propose the config

Write `.hexagonal.json` from the real paths, using [assets/hexagonal.example.json](assets/hexagonal.example.json) as the shape. Keys: `core`, `ports`, `driving_adapters`, `driven_adapters`, `composition_root`, `forbidden_in_core`. Show the proposed file and wait for approval before writing it.

### 5. Add the CI contract

Pick the template for the repo language and show the diff before applying it. The rule must fail on a deliberate violation, not only pass on correct code.

- Python: [assets/python/importlinter.ini](assets/python/importlinter.ini)
- TypeScript and JavaScript: [assets/typescript/.dependency-cruiser.cjs](assets/typescript/.dependency-cruiser.cjs)
- Java: [assets/java/HexagonalArchitectureTest.java](assets/java/HexagonalArchitectureTest.java)
- Go: [assets/go/.go-arch-lint.yml](assets/go/.go-arch-lint.yml)
- Workflow for all languages: [assets/ci/architecture.yml](assets/ci/architecture.yml)

Details and the false-green traps are in [references/enforcement.md](references/enforcement.md).

### 6. Migrate incrementally

One use case or one adapter per PR. Never a big bang. The order that costs least: freeze behaviour with tests, extract the driven port and its in-memory double, move the use case into the core, put the real adapter behind the port, move the driving adapter, then gather construction in the composition root. Branch `refactoring/<issue>-<context>` and draft PR follow the `github-practices` skill if it is installed; otherwise use the same format. The full step list, the stopping signals and the PR checklist are in [references/migration.md](references/migration.md).

### 7. Re-audit

Run the audit again after each PR and compare by severity and area, not only the total. A new high finding offset by resolved medium ones is still a regression. If high findings increase, the PR is fixed or reverted; they must go down or stay level.

## Safety rules

- Nothing is written or pushed without an explicit OK for that change, showing the diff or command and how to undo it.
- Asking for the migration is the request, not the OK. Show the plan and wait.
- If you cannot ask, apply nothing: hand over the plan and stop.
- No big-bang rewrite, no deleting the old path before the new one is tested.
- The audit is heuristic; never present a zero as proof that the architecture is correct.
- On a contradiction between this skill and the repo `CONTRIBUTING.md`, the repo wins.

## Where things are

References (read only the one you need):

| File | When to read it |
|---|---|
| [references/principles.md](references/principles.md) | The nine principles, glossary, common misunderstandings and the mistakes found in tier 3 articles |
| [references/when-to-apply.md](references/when-to-apply.md) | Decide apply, partial or skip, and understand the real costs |
| [references/layouts.md](references/layouts.md) | Propose a structure in Python, TypeScript, Java or Go |
| [references/testing.md](references/testing.md) | Design unit, acceptance, integration and system tests with in-memory doubles |
| [references/migration.md](references/migration.md) | Plan and execute a strangler migration one use case at a time |
| [references/enforcement.md](references/enforcement.md) | Add the CI contract for each language and check that it bites |

Scripts (run them, do not read them):

| File | What for |
|---|---|
| [scripts/audit.py](scripts/audit.py) | Read-only audit with `--path`, `--config`, `--json` |

Assets (copy, do not edit):

| File | What to copy |
|---|---|
| [assets/hexagonal.example.json](assets/hexagonal.example.json) | Shape of `.hexagonal.json` with real paths |
| [assets/python/importlinter.ini](assets/python/importlinter.ini) | import-linter contracts for Python |
| [assets/typescript/.dependency-cruiser.cjs](assets/typescript/.dependency-cruiser.cjs) | dependency-cruiser rules for TypeScript and JavaScript |
| [assets/java/HexagonalArchitectureTest.java](assets/java/HexagonalArchitectureTest.java) | ArchUnit test for Java |
| [assets/go/.go-arch-lint.yml](assets/go/.go-arch-lint.yml) | go-arch-lint components for Go |
| [assets/ci/architecture.yml](assets/ci/architecture.yml) | GitHub Actions workflow, one job per language |
| [assets/agent-permissions/opencode.json](assets/agent-permissions/opencode.json) | OpenCode permission block that asks before push, commit or PR |
| [assets/agent-permissions/claude-settings.json](assets/agent-permissions/claude-settings.json) | Claude Code equivalent: asks before commit, push or PR |
