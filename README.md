# hexagonal-architecture

[![CI](https://github.com/iDiagoValeta/hexagonal-architecture/actions/workflows/ci.yml/badge.svg)](https://github.com/iDiagoValeta/hexagonal-architecture/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Claude Code skill (also for OpenCode and other AI agents) that audits a repository against hexagonal architecture (ports and adapters) and applies only the changes you approve. It checks the dependency rule in the code, not just the folder layout: domain isolation, adapter-to-adapter imports, and construction outside the composition root. It also proposes the architecture linting contract for the repo language: import-linter for Python, dependency-cruiser for TypeScript, ArchUnit for Java and go-arch-lint for Go.

Use it when the core of a codebase is drifting toward a framework, when clean architecture or DDD is being discussed without evidence, or when a migration to ports and adapters has to be planned without a big-bang rewrite. When the repo does not justify the pattern, it recommends not migrating and explains why.

## What it checks

- Core code that imports an adapter, an ORM, a framework, an HTTP client or a database driver.
- Framework annotations or decorators in the core: Spring style annotations in Java (`@Service`, `@Entity`, `@Transactional`) and web route decorators in Python (`@app.get`, `@api_view`).
- Adapters that import each other.
- Adapters instantiated outside the composition root.
- Ports named after a technology (`PostgresPort`, `HttpGateway`).
- A controller or a route handler sitting under a ports folder.
- A driven port without an in-memory double in tests.
- A core with no tests isolated from infrastructure.
- Python tests that `python3 -m unittest` discovers as zero without failing (no `__init__.py` and no pytest config).
- A structure it cannot recognise, reported as info with a `.hexagonal.json` proposal.

Findings come in four severities: high (the dependency rule is broken), medium (the structure leaks), low (naming and hygiene) and info (not enough evidence). A green audit is not proof: it only means the script did not see the violations it knows how to look for.

## Quick start

```bash
git clone https://github.com/iDiagoValeta/hexagonal-architecture.git
cd hexagonal-architecture && ./install.sh
```

Then in Claude Code or OpenCode:

```text
/hexagonal-architecture
```

## Example

This tree breaks the dependency rule: the domain imports SQLAlchemy.

```text
/tmp/hex-demo
└── src
    ├── domain/order.py                # imports sqlalchemy.orm
    ├── ports/order_repository.py
    ├── adapters/driven/sql_orders.py
    └── main.py                        # composition root
```

The domain file:

```python
from dataclasses import dataclass

from sqlalchemy.orm import Session
```

`python3 hexagonal-architecture/scripts/audit.py --path /tmp/hex-demo` prints:

```text
# Hexagonal architecture audit

- Path: `/tmp/hex-demo`
- Configuration: inferred from folder names (no `.hexagonal.json`)

## Findings

### High (1)

- **[high] core.forbidden-library** (core) `src/domain/order.py:3`: The core imports `sqlalchemy.orm`, a library for IO, a framework or persistence (matches `sqlalchemy`).
  - Fix: Move that dependency behind a port and keep the library in an adapter.

...

## Summary

| Severity | Findings |
| --- | --- |
| High | 1 |
| Medium | 2 |
| Low | 0 |
| Info | 0 |

...
```

The trimmed medium findings are the driven port without an in-memory double and the core without isolated tests.

## Install

### Claude Code

```bash
./install.sh
```

It creates the symlink `~/.claude/skills/hexagonal-architecture` pointing to `hexagonal-architecture/` in this repo. The skill is Markdown, two Python scripts and copyable CI and permission templates, so a Claude Code skill needs no plugin runtime. It is idempotent: if it already exists and points here, it does nothing; if something else exists at that path, it aborts without deleting it.

### OpenCode

OpenCode also reads `~/.claude/skills/`, so the same command works:

```bash
./install.sh
```

### Per project

Copy the skill into the repo where you want to use it:

```bash
mkdir -p .claude/skills
cp -r /path/to/hexagonal-architecture/hexagonal-architecture .claude/skills/
```

That way it is versioned with the project and available only there.

### Uninstall

```bash
./install.sh --uninstall
```

It removes the symlink only if it points to this repo. If it points elsewhere, or the path holds a real directory or file, it aborts without touching it.

## Usage

In Claude Code or OpenCode:

```text
/hexagonal-architecture
```

Or ask in natural language: "audit this repo for hexagonal architecture", "my domain imports SQLAlchemy", "add a dependency rule to CI", "can I migrate this CRUD app?".

The flow is always the same: audit in read-only mode, report by severity, decide apply, partial or skip with reasons, propose `.hexagonal.json` and the CI contract for the repo language, migrate one use case or adapter per PR, and re-audit. High findings must go down or stay level. Nothing is written, committed, pushed or opened as a PR without an explicit OK for that specific change in the request.

## Approval gate

Asking for a migration is a request, not an approval. The agent shows the exact diff or command and how to undo it, then waits for an answer. Instructions alone are not enough for some AI agents, so the repo ships permission blocks that turn a commit, a push or a PR into a prompt:

- OpenCode: merge `hexagonal-architecture/assets/agent-permissions/opencode.json` into the project `opencode.json` or into `~/.config/opencode/opencode.json`.
- Claude Code: merge `hexagonal-architecture/assets/agent-permissions/claude-settings.json` into `.claude/settings.json`.

The block allows everything except `git commit`, `git push` and `gh pr`, so history and remote changes wait for a prompt. It does not gate file edits: those remain covered by the instruction in `SKILL.md`. In a non-interactive run the agent stops instead of committing or pushing.

## Structure

```text
.
├── hexagonal-architecture/
│   ├── SKILL.md                Entry point: gate, flow, severity and file map
│   ├── references/
│   │   ├── principles.md       Nine principles, glossary, common mistakes, tiered sources
│   │   ├── when-to-apply.md    Apply, partial or skip, with real costs
│   │   ├── layouts.md          Reference layouts in Python, TypeScript, Java and Go
│   │   ├── testing.md          Unit, acceptance, integration and system tests
│   │   ├── migration.md        Strangler migration one use case at a time
│   │   └── enforcement.md      CI contracts per language and false greens
│   ├── scripts/
│   │   ├── audit.py            Read-only audit
│   │   └── imports.py          Import extraction used by the audit
│   └── assets/
│       ├── hexagonal.example.json  Shape of .hexagonal.json
│       ├── python/             import-linter template
│       ├── typescript/         dependency-cruiser template
│       ├── java/               ArchUnit template
│       ├── go/                 go-arch-lint template
│       ├── ci/                 GitHub Actions workflow
│       └── agent-permissions/  Permission gates for OpenCode and Claude Code
├── evals/
│   └── evals.json              Three scenarios for discovery and behaviour
├── tests/
│   ├── test_audit.py           Audit rules over temporary trees
│   ├── test_imports.py         Import extraction per language
│   └── test_skill_format.py    Frontmatter, size, links and forbidden characters
├── .github/workflows/ci.yml    Python 3.12 tests and install.sh syntax
├── install.sh                  Symlink installer and safe uninstaller
├── LICENSE                     MIT
└── README.md
```

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
```

The tests validate the audit and import extraction, the format of `SKILL.md` (frontmatter, size, links and forbidden characters); `bash -n install.sh` checks the installer syntax. CI runs both on Python 3.12.

## Requirements

- Python 3 for the audit. Standard library only, no dependencies to install; CI runs 3.12.
- bash for `install.sh`, which creates a symlink under `~/.claude/skills` (Linux and macOS).
- No network access: the audit only reads the files under `--path`.
- `gh` CLI only if you want the agent to open the PR, and only after you approve it.

## License

MIT, see [LICENSE](LICENSE).

## Sources

The principles come from Alistair Cockburn and Juan Manuel Garrido de Paz. AWS Prescriptive Guidance, Netflix, Thoughtworks and The Software House add practice. Two tier 3 articles are included as worked examples of common mistakes, not as authority on the definition. The full tiered list is in `hexagonal-architecture/references/principles.md`.

See also: [github-practices](https://github.com/iDiagoValeta/github-practices)
