# hexagonal-architecture

[![CI](https://github.com/iDiagoValeta/hexagonal-architecture/actions/workflows/ci.yml/badge.svg)](https://github.com/iDiagoValeta/hexagonal-architecture/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An agent skill for AI coding agents that audits a repository against hexagonal architecture (ports and adapters) and applies only the changes you approve. It works in Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Windsurf, ZCode and any agent that reads the open [SKILL.md format](https://agentskills.io). It checks the dependency rule in the code, not just the folder layout: domain isolation, adapter-to-adapter imports, and construction outside the composition root. It also proposes the architecture linting contract for the repo language: import-linter for Python, dependency-cruiser for TypeScript, ArchUnit for Java and go-arch-lint for Go.

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

Install with the skills CLI, naming your agent:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a <agent>
```

Or with the GitHub CLI, which needs a recent `gh` with the skill command in preview:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent <agent> --scope user
```

`gh skill` supports every listed agent except Windsurf and ZCode, which use the skills CLI or `install.sh`.

`<agent>` is one of `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot`, `opencode`, `windsurf` or `zcode`. See [Install](#install) for the install options for each agent, the manual symlink and how to invoke the skill.

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

Every agent reads the same `hexagonal-architecture/` folder and the same `SKILL.md`; only the skills directory and the install command change. The table summarises the paths; the sections below give the commands for each agent, alphabetically.

| Agent | `--agent` value | User dir | Project dir | How to invoke |
|---|---|---|---|---|
| Claude Code | `claude-code` | `~/.claude/skills` | `.claude/skills` | `/hexagonal-architecture`, or `/hexagonal-architecture:hexagonal-architecture` as a plugin |
| Codex | `codex` | `~/.agents/skills` | `.agents/skills` | `$hexagonal-architecture`, or `/skills` to pick it |
| Cursor | `cursor` | `~/.cursor/skills` | `.cursor/skills` or `.agents/skills` | type `/` in the Agent chat and pick `hexagonal-architecture` |
| Gemini CLI | `gemini-cli` | `~/.gemini/skills` | `.gemini/skills` or `.agents/skills` | activated from the description; `/skills list` shows it |
| GitHub Copilot | `github-copilot` | `~/.copilot/skills` | `.github/skills`, `.claude/skills` or `.agents/skills` | loaded automatically when relevant |
| OpenCode | `opencode` | `~/.config/opencode/skills` | `.opencode/skills`, `.claude/skills` or `.agents/skills` | `/hexagonal-architecture` |
| Windsurf | `windsurf` | `~/.codeium/windsurf/skills` | `.windsurf/skills` or `.agents/skills` | `/hexagonal-architecture` |
| ZCode | `zcode` | `~/.zcode/skills` | `.zcode/skills` | ask in natural language |

Codex installs into the shared `~/.agents/skills`, which Cursor, Gemini CLI, GitHub Copilot, OpenCode and Windsurf also read. `pnpm dlx skills add` does the same as `npx skills add`; without `-g` the skills CLI installs into the project, and `-g` selects the user scope.

### Claude Code

Native plugin, one step on Claude Code 2.1.275 or later:

```text
/plugin install hexagonal-architecture --marketplace iDiagoValeta/hexagonal-architecture
```

Two steps on any version with plugins:

```bash
claude plugin marketplace add iDiagoValeta/hexagonal-architecture
claude plugin install hexagonal-architecture@hexagonal-architecture
```

The marketplace is the repo itself, so there is nothing else to host. To remove the plugin and its marketplace entry:

```bash
claude plugin marketplace remove hexagonal-architecture
```

It also uninstalls the plugins it provided and deletes their saved options and data.

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a claude-code
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent claude-code --scope user
```

Manual:

```bash
./install.sh claude-code
```

It creates the symlink `~/.claude/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.claude/skills/`.

Invoke it as `/hexagonal-architecture`, or as `/hexagonal-architecture:hexagonal-architecture` when installed as a plugin.

### Codex

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a codex
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent codex --scope user
```

Manual:

```bash
./install.sh codex
```

Codex reads the shared `~/.agents/skills`, so the link lives there. For one project, copy `hexagonal-architecture/` into `.agents/skills/`.

Invoke it as `$hexagonal-architecture`, or run `/skills` and pick it from the list.

### Cursor

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a cursor
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent cursor --scope user
```

Manual:

```bash
./install.sh cursor
```

It creates the symlink `~/.cursor/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.cursor/skills/` or `.agents/skills/`.

Invoke it by typing `/` in the Agent chat and picking `hexagonal-architecture`.

### Gemini CLI

Native installer:

```bash
gemini skills install https://github.com/iDiagoValeta/hexagonal-architecture.git --consent
```

Add `--scope workspace` for the project. It finds the skill in the repo subfolder on its own.

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a gemini-cli
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent gemini-cli --scope user
```

Manual:

```bash
./install.sh gemini-cli
```

It creates the symlink `~/.gemini/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.gemini/skills/` or `.agents/skills/`.

Gemini CLI activates it from the description when the request matches; `/skills list` shows it.

### GitHub Copilot

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a github-copilot
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent github-copilot --scope user
```

Manual:

```bash
./install.sh github-copilot
```

It creates the symlink `~/.copilot/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.github/skills/`, `.claude/skills/` or `.agents/skills/`.

GitHub Copilot loads it automatically when relevant.

### OpenCode

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a opencode
```

GitHub CLI:

```bash
gh skill install iDiagoValeta/hexagonal-architecture hexagonal-architecture --agent opencode --scope user
```

Manual:

```bash
./install.sh opencode
```

It creates the symlink `~/.config/opencode/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.opencode/skills/`, `.claude/skills/` or `.agents/skills/`.

OpenCode also reads `~/.claude/skills/` and `~/.agents/skills/`. Invoke it as `/hexagonal-architecture`.

### Windsurf

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a windsurf
```

`gh skill` does not support Windsurf; use the skills CLI or the manual install.

Manual:

```bash
./install.sh windsurf
```

It creates the symlink `~/.codeium/windsurf/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.windsurf/skills/` or `.agents/skills/`.

Invoke it as `/hexagonal-architecture`.

### ZCode

Skills CLI:

```bash
npx skills add iDiagoValeta/hexagonal-architecture -a zcode
```

`gh skill` does not support ZCode; use the skills CLI or the manual install.

Manual:

```bash
./install.sh zcode
```

It creates the symlink `~/.zcode/skills/hexagonal-architecture`. For one project, copy `hexagonal-architecture/` into `.zcode/skills/`.

Ask ZCode in natural language, for example "audit this repo for hexagonal architecture".

### Any other agent

Any agent that reads the open SKILL.md format works the same way: copy the `hexagonal-architecture/` folder into the skills directory your agent documents.

```bash
git clone https://github.com/iDiagoValeta/hexagonal-architecture.git
cp -r hexagonal-architecture/hexagonal-architecture <agent-skills-dir>/
```

### install.sh

From a clone of this repo:

```bash
git clone https://github.com/iDiagoValeta/hexagonal-architecture.git
cd hexagonal-architecture
./install.sh AGENT...
./install.sh --uninstall AGENT...
./install.sh --list
```

`AGENT` is one of `claude-code`, `codex`, `cursor`, `gemini-cli`, `github-copilot`, `opencode`, `windsurf` or `zcode`. It creates a symlink to `hexagonal-architecture/` in this repo at the user directory of the agent; `codex` targets the shared `~/.agents/skills`. `--list` prints every agent with the path it uses.

It is idempotent: if the link already exists and points here, it does nothing; if something else exists at that path, it aborts without deleting it. Several agents in one call are all processed, and the exit status is 1 if any failed. No arguments or an unknown agent print the usage on stderr and exit 2.

Uninstall removes the symlink only if it points to this repo. If it points elsewhere, or the path holds a real directory or file, it aborts without touching it:

```bash
./install.sh --uninstall claude-code
```

## Usage

Invoke the skill the way your agent does, as the table above says, or ask in natural language: "audit this repo for hexagonal architecture", "my domain imports SQLAlchemy", "add a dependency rule to CI", "can I migrate this CRUD app?".

The flow is always the same: audit in read-only mode, report by severity, decide apply, partial or skip with reasons, propose `.hexagonal.json` and the CI contract for the repo language, migrate one use case or adapter per PR, and re-audit. High findings must go down or stay level. Nothing is written, committed, pushed or opened as a PR without an explicit OK for that specific change in the request.

## Approval gate

Asking for a migration is a request, not an approval. The agent shows the exact diff or command and how to undo it, then waits for an answer. Instructions alone are not enough for some AI agents, so Claude Code and OpenCode ship permission blocks that turn a commit, a push or a PR into a prompt:

- Claude Code: merge `hexagonal-architecture/assets/agent-permissions/claude-settings.json` into `.claude/settings.json`.
- OpenCode: merge `hexagonal-architecture/assets/agent-permissions/opencode.json` into the project `opencode.json` or into `~/.config/opencode/opencode.json`.

The block allows everything except `git commit`, `git push` and `gh pr`, so history and remote changes wait for a prompt. It does not gate file edits: those remain covered by the instruction in `SKILL.md`. In a non-interactive run the agent stops instead of committing or pushing. Other agents rely only on the gate written in `SKILL.md`, which is the weaker of the two: check that your agent asks before the first change.

## Structure

```text
.
├── .claude-plugin/             Claude Code plugin and marketplace manifests
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
│   ├── test_install.py         Installer and safe uninstall
│   └── test_skill_format.py    Frontmatter, size, links and forbidden characters
├── .github/workflows/ci.yml    Python 3.12 tests and install.sh syntax
├── install.sh                  Symlink installer for every agent and safe uninstaller
├── LICENSE                     MIT
└── README.md
```

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
```

The tests validate the audit and import extraction, the format of `SKILL.md` (frontmatter, size, links and forbidden characters) and the installer and uninstaller in temporary directories; `bash -n install.sh` checks the installer syntax. CI runs both on Python 3.12.

## Requirements

- An agent that supports Agent Skills, such as any of the agents above.
- Node.js 22.20 or later with `npx` for the skills CLI, or the GitHub CLI with the skill command in preview for `gh skill`.
- Python 3 for the audit. Standard library only, no dependencies to install; CI runs 3.12.
- bash for `install.sh`, which creates a symlink under the user skills directory of the agent (Linux and macOS).
- No network access: the audit only reads the files under `--path`.
- `gh` CLI for the `gh skill` install, and to let the agent open the PR after you approve it.

## License

MIT, see [LICENSE](LICENSE).

## Sources

The principles come from Alistair Cockburn and Juan Manuel Garrido de Paz. AWS Prescriptive Guidance, Netflix, Thoughtworks and The Software House add practice. Two tier 3 articles are included as worked examples of common mistakes, not as authority on the definition. The full tiered list is in `hexagonal-architecture/references/principles.md`.

See also: [github-practices](https://github.com/iDiagoValeta/github-practices)
