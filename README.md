# hexagonal-architecture

Portable skill for Claude Code and OpenCode that audits a repository against hexagonal architecture (ports and adapters) and applies only the changes you approve.

It looks for core code that imports adapters, frameworks or IO libraries, adapters that import each other, adapters instantiated outside the composition root, ports named after technology, and driven ports without an in-memory double. When the repo does not justify the pattern, it recommends not migrating and explains why.

## Install

### Claude Code

```bash
./install.sh
```

It creates the symlink `~/.claude/skills/hexagonal-architecture` pointing to `hexagonal-architecture/` in this repo. It is idempotent: if it already exists and points here, it does nothing; if something else exists at that path, it aborts without deleting it.

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

Asking for a migration is a request, not an approval. The agent shows the exact diff or command and how to undo it, then waits for an answer. Instructions alone are not enough for some models, so the repo ships permission blocks that turn a commit, a push or a PR into a prompt:

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
└── README.md
```

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
```

The tests validate the audit and import extraction, the format of `SKILL.md` (frontmatter, size, links and forbidden characters) and the syntax of `install.sh`. CI runs the same on Python 3.12.

## Origin

The principles come from Alistair Cockburn and Juan Manuel Garrido de Paz. AWS Prescriptive Guidance, Netflix, Thoughtworks and The Software House add practice. Two tier 3 articles are included as worked examples of common mistakes, not as authority on the definition. The full tiered list is in `hexagonal-architecture/references/principles.md`.

The skill structure follows the sibling `github-practices` skill and reuses its safe install and approval gate patterns.
