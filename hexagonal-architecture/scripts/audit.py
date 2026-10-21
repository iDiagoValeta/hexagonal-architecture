#!/usr/bin/env python3
"""Read-only audit of a repository against hexagonal architecture.

Deliberate separation: `collect` talks to the filesystem; the rest works on a
state with files already read and their roles. The rules are tested with
temporary trees, so the skill does not depend on the model improvising the
review.

Usage:
    audit.py [--path .] [--config .hexagonal.json] [--json]

Exits 0 if the audit completes even when there are findings, 1 if the config
cannot be read and 2 if the audited path does not exist.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path, PurePosixPath

from imports import IGNORED, extract_imports, mask, resolve

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

# Default lists per language. Configuration can only extend them: a rule that
# can be turned off from the audited repo stops being a rule.
FORBIDDEN_IN_CORE = {
    "python": [
        "sqlalchemy",
        "psycopg2",
        "pymongo",
        "redis",
        "requests",
        "httpx",
        "boto3",
        "fastapi",
        "flask",
        "django",
    ],
    "ts": [
        "express",
        "fastify",
        "axios",
        "pg",
        "mysql2",
        "mongoose",
        "prisma",
        "@prisma/client",
        "typeorm",
        "@aws-sdk",
    ],
    "java": [
        "org.springframework",
        "jakarta",
        "javax.persistence",
        "java.sql",
        "java.net.http",
        "org.hibernate",
        "com.amazonaws",
        "software.amazon.awssdk",
        "com.google.cloud",
        "com.azure",
    ],
    "go": [
        "net/http",
        "database/sql",
        "gorm.io",
        "github.com/aws",
        "github.com/lib/pq",
        "github.com/jackc/pgx",
        "github.com/go-sql-driver/mysql",
        "go.mongodb.org/mongo-driver",
        "github.com/redis/go-redis",
        "github.com/gin-gonic/gin",
        "github.com/labstack/echo",
        "github.com/gofiber/fiber",
    ],
}
FORBIDDEN_IN_CORE["js"] = FORBIDDEN_IN_CORE["ts"]

CORE = {"domain", "core", "application", "usecases", "use_cases", "usecase", "entities", "model"}
PORTS = {"ports", "port"}
DRIVING = {
    "driving",
    "inbound",
    "entrypoints",
    "entrypoint",
    "api",
    "web",
    "cli",
    "controllers",
    "controller",
    "http",
    "rest",
    "graphql",
    "handlers",
    "handler",
}
DRIVEN = {
    "driven",
    "outbound",
    "infrastructure",
    "infra",
    "persistence",
    "repositories",
    "repository",
    "db",
    "storage",
    "messaging",
    "gateway",
}
# A flat adapters folder whose files do not sit under a driving or driven
# folder. It is an adapter, but its family is unknown.
ADAPTERS = {"adapters", "adapter"}
COMPOSITION = {"composition", "di", "bootstrap", "wiring"}
COMPOSITION_NAMES = {
    "main",
    "bootstrap",
    "container",
    "wiring",
    "composition_root",
}
ADAPTER_ROLES = ("driving", "driven", "adapters")
TEST_WORDS = {"test", "tests", "spec", "specs", "__tests__", "testdata"}

TECHNOLOGIES = {
    "postgres",
    "postgresql",
    "mysql",
    "sqlite",
    "mongo",
    "mongodb",
    "redis",
    "memcached",
    "kafka",
    "rabbitmq",
    "sqs",
    "sns",
    "http",
    "https",
    "rest",
    "grpc",
    "soap",
    "graphql",
    "sql",
    "jdbc",
    "jpa",
    "hibernate",
    "s3",
    "aws",
    "gcp",
    "azure",
    "smtp",
    "ftp",
    "filesystem",
    "sqlalchemy",
    "dynamodb",
    "elasticsearch",
}

# A driven port is what the application needs from the outside. Without an
# explicit list in the config it is recognized by the purpose in the name.
DRIVEN_WORDS = {
    "repository",
    "repo",
    "gateway",
    "client",
    "store",
    "storage",
    "dao",
    "publisher",
    "sender",
    "notifier",
    "mailer",
    "queue",
    "bus",
    "cache",
    "spi",
    "storing",
    "saving",
    "persisting",
}
# A framework `Mock` is not an in-memory double; the purpose markers below
# are the ones that describe one.
DOUBLE_MARKERS = {"inmemory", "fake", "stub", "double"}
# Words that make a file or a class look like an adapter rather than a
# supporting model of the adapter that owns it.
ADAPTER_WORDS = DRIVEN_WORDS | DRIVING | {
    "adapter",
    "adapters",
    "double",
    "fake",
    "memory",
    "stub",
}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "ts",
    ".tsx": "ts",
    ".js": "ts",
    ".jsx": "ts",
    ".mjs": "ts",
    ".cjs": "ts",
    ".java": "java",
    ".kt": "java",
    ".go": "go",
}

CLASS_RE = re.compile(r"\bclass\s+([A-Za-z_]\w*)")
GO_STRUCT_RE = re.compile(r"\btype\s+([A-Za-z_]\w*)\s+struct\b")

# Framework annotations that must not live in the core. They are matched on
# the masked text (comments and string literals blanked).
FRAMEWORK_ANNOTATIONS = (
    "Service",
    "Component",
    "Autowired",
    "Entity",
    "Table",
    "Repository",
    "RestController",
    "Controller",
    "Transactional",
)
FRAMEWORK_ANNOTATION_RE = re.compile(
    r"@(?:%s)\b" % "|".join(FRAMEWORK_ANNOTATIONS)
)

# Python has no annotations, so the equivalent signal is a framework
# decorator: a route attribute on a web object, a known framework helper or a
# dotted name owned by a forbidden framework. Imports of those frameworks are
# already reported by `core.forbidden-library`.
PYTHON_DECORATOR_RE = re.compile(
    r"^\s*@([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)", re.MULTILINE
)
WEB_ROUTE_ATTRIBUTES = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "route",
    "middleware",
    "exception_handler",
    "websocket",
}
WEB_OBJECT_NAMES = {
    "app",
    "router",
    "blueprint",
    "bp",
    "api",
    "routes",
    "server",
    "application",
}
FRAMEWORK_DECORATOR_NAMES = {"api_view", "require_http_methods"}

# Content signals that a file under a ports folder is really a driving adapter.
PORT_ADAPTER_RE = re.compile(
    r"@(?:RestController|GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping)\b"
    r"|\b(?:router|app)\.(?:get|post|put|patch|delete|use|all)\s*\("
    r"|\bAPIRouter\b"
)


# ---------------------------------------------------------------------------
# Collection (impure): the only part that touches the disk.
# ---------------------------------------------------------------------------


def _language(relative):
    return LANGUAGE_EXTENSIONS.get(PurePosixPath(relative).suffix.lower())


def _pytest_config(root):
    """Whether the repo configures pytest, which makes it skip discovery."""
    if (root / "pytest.ini").is_file():
        return True
    for name, marker in (
        ("pyproject.toml", "[tool.pytest"),
        ("setup.cfg", "[tool:pytest]"),
    ):
        path = root / name
        if not path.is_file():
            continue
        try:
            if marker in path.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            continue
    return False


def collect(root, config_path=None):
    """Read config and source files. Return a serializable state."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(str(root))

    candidate = Path(config_path).expanduser() if config_path else root / ".hexagonal.json"
    config = None
    if candidate.is_file():
        try:
            config = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("config is not valid JSON: %s" % exc) from exc
        if not isinstance(config, dict):
            raise ValueError("config must be a JSON object")
    elif config_path:
        raise ValueError("config does not exist: %s" % candidate)

    files = {}
    for directory, subdirectories, names in _walk(root):
        for name in names:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if _language(relative) is None:
                continue
            try:
                files[relative] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

    return {
        "root": str(root),
        "files": files,
        "config": config,
        "config_file": str(candidate) if config is not None else None,
        "pytest_config": _pytest_config(root),
    }


def _walk(root):
    for directory, subdirectories, names in os.walk(root):
        subdirectories[:] = [
            name for name in subdirectories if name not in IGNORED
        ]
        yield directory, subdirectories, names


# ---------------------------------------------------------------------------
# Evaluation (deterministic): input state, output findings.
# ---------------------------------------------------------------------------


def _finding(finding_id, area, severity, file, line, message, fix):
    return {
        "id": finding_id,
        "area": area,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
        "fix": fix,
    }


def _normalize(path):
    return PurePosixPath(str(path).replace("\\", "/")).as_posix().lstrip("./").rstrip("/")


def _is_test(relative):
    parts = [part.lower() for part in relative.split("/")]
    if any(part in TEST_WORDS for part in parts[:-1]):
        return True
    name = parts[-1]
    return (
        name.startswith("test_")
        or name.endswith((".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.js"))
        or name.endswith(("_test.py", "_test.go", "_test.java", "test.java", "tests.java"))
        or name.endswith("test.java")
        or name.endswith("test.kt")
    )


def _config_prefixes(config):
    pairs = []
    for key, role in (
        ("core", "core"),
        ("ports", "ports"),
        ("driving_adapters", "driving"),
        ("driven_adapters", "driven"),
        ("composition_root", "composition"),
    ):
        for value in config.get(key) or []:
            prefix = _normalize(value)
            if prefix:
                pairs.append((prefix, role))
    return sorted(pairs, key=lambda pair: len(pair[0]), reverse=True)


def _role_by_folder(relative):
    parts = relative.split("/")
    matches = []
    for index, part in enumerate(parts[:-1]):
        name = part.lower()
        if name in DRIVING:
            matches.append(("driving", 0, index))
        elif name in DRIVEN:
            matches.append(("driven", 1, index))
        elif name in PORTS:
            matches.append(("ports", 2, index))
        elif name in CORE:
            matches.append(("core", 3, index))
        elif name in COMPOSITION:
            matches.append(("composition", 4, index))
    if not matches:
        # A bare `adapters` folder carries no family, but it is still an
        # adapter and must not fall through to `other`.
        for index, part in enumerate(parts[:-1]):
            if part.lower() in ADAPTERS:
                return "adapters", "/".join(parts[: index + 1])
        return None
    role, _, index = sorted(matches, key=lambda item: (item[1], item[2]))[0]
    return role, "/".join(parts[: index + 1])


def _classify(relative, config):
    """Return (role, prefix that justifies it)."""
    if _is_test(relative):
        return "other", None

    for prefix, role in _config_prefixes(config or {}):
        if relative == prefix or relative.startswith(prefix + "/"):
            return role, prefix

    inferred = _role_by_folder(relative)
    if inferred:
        return inferred

    stem = PurePosixPath(relative).stem
    if stem.lower() in COMPOSITION_NAMES:
        return "composition", relative
    # Only the Java entry point class is `Application.java`; a Python,
    # TypeScript or Go `application` module is an ordinary file.
    if stem == "Application" and _language(relative) == "java":
        return "composition", relative
    return "other", None


def _classify_all(state):
    return {
        relative: _classify(relative, state["config"])
        for relative in state["files"]
    }


def _unit(relative, role, prefix):
    """Group files of the same adapter so internal imports are allowed.

    Files directly under the family folder are separate adapters: grouping
    them all in the prefix hid imports between two adapters of one family.
    A subfolder is one adapter, so its files belong to the same unit.
    """
    if role not in ADAPTER_ROLES:
        return None
    if prefix and relative.startswith(prefix + "/"):
        rest = relative[len(prefix) + 1 :].split("/")
        return prefix + "/" + rest[0]
    return str(PurePosixPath(relative).parent)


def _extracted(state):
    return {
        relative: extract_imports(text, _language(relative))
        for relative, text in state["files"].items()
    }


def _forbidden(config, language):
    patterns = list(FORBIDDEN_IN_CORE.get(language, []))
    for extra in (config or {}).get("forbidden_in_core") or []:
        if extra not in patterns:
            patterns.append(extra)
    return patterns


def _matches(module, pattern):
    module = module.lower()
    pattern = str(pattern).lower()
    return (
        module == pattern
        or module.startswith(pattern + ".")
        or module.startswith(pattern + "/")
    )


def _check_core_imports_adapter(state, roles, extracted):
    findings = []
    for relative, imports in extracted.items():
        if roles[relative][0] != "core":
            continue
        language = _language(relative)
        for line, module in imports:
            target = resolve(module, relative, state["root"], language)
            target_role = roles.get(target, ("other", None))[0] if target else None
            if target_role in ADAPTER_ROLES:
                findings.append(
                    _finding(
                        "core.imports-adapter",
                        "core",
                        "high",
                        relative,
                        line,
                        "The core imports `%s`, which is an adapter (%s)."
                        % (module, target_role),
                        "Depend on a port (an interface of your own) and move the "
                        "concrete call to the composition root.",
                    )
                )
    return findings


def _check_core_library(state, roles, extracted):
    findings = []
    for relative, imports in extracted.items():
        if roles[relative][0] != "core":
            continue
        patterns = _forbidden(state["config"], _language(relative))
        for line, module in imports:
            if module.startswith("."):
                continue
            for pattern in patterns:
                if _matches(module, pattern):
                    findings.append(
                        _finding(
                            "core.forbidden-library",
                            "core",
                            "high",
                            relative,
                            line,
                            "The core imports `%s`, a library for IO, a framework "
                            "or persistence (matches `%s`)." % (module, pattern),
                            "Move that dependency behind a port and keep the "
                            "library in an adapter.",
                        )
                    )
                    break
    return findings


def _check_core_framework_annotation(state, roles):
    findings = []
    patterns = _forbidden(state["config"], "python")
    for relative, text in state["files"].items():
        if roles[relative][0] != "core":
            continue
        language = _language(relative)
        if language not in ("java", "python"):
            continue
        masked = mask(text, language)
        if language == "java":
            for match in FRAMEWORK_ANNOTATION_RE.finditer(masked):
                line = masked.count("\n", 0, match.start()) + 1
                findings.append(
                    _finding(
                        "core.framework-annotation",
                        "core",
                        "high",
                        relative,
                        line,
                        "The core uses the framework annotation `%s`."
                        % match.group(0),
                        "Remove the framework annotation from the core and apply "
                        "it in the adapter that wires this object.",
                    )
                )
            continue
        for match in PYTHON_DECORATOR_RE.finditer(masked):
            name = match.group(1)
            parts = name.split(".")
            if not _is_framework_decorator(parts, patterns):
                continue
            line = masked.count("\n", 0, match.start()) + 1
            findings.append(
                _finding(
                    "core.framework-annotation",
                    "core",
                    "high",
                    relative,
                    line,
                    "The core uses the framework decorator `@%s`." % name,
                    "Remove the framework decorator from the core and handle the "
                    "transport concern in a driving adapter.",
                )
            )
    return findings


def _is_framework_decorator(parts, patterns):
    if any(_matches(parts[0], pattern) for pattern in patterns):
        return True
    if len(parts) >= 2:
        return (
            parts[-1].lower() in WEB_ROUTE_ATTRIBUTES
            and parts[-2].lower() in WEB_OBJECT_NAMES
        )
    return parts[0].lower() in FRAMEWORK_DECORATOR_NAMES


def _defines_adapter(relative, text):
    """Whether the file or one of its classes is named like an adapter.

    A module in an adapter folder can be a supporting model (`order_row.py`,
    `OrderRow`), not a second adapter. Only adapter-like files count for the
    rule that adapters do not import each other.
    """
    language = _language(relative)
    pattern = GO_STRUCT_RE if language == "go" else CLASS_RE
    names = [PurePosixPath(relative).stem]
    names += [match.group(1) for match in pattern.finditer(mask(text, language))]
    return any(_words(name) & ADAPTER_WORDS for name in names)


def _check_adapter_imports_adapter(state, roles, extracted):
    findings = []
    for relative, imports in extracted.items():
        role, prefix = roles[relative]
        if role not in ADAPTER_ROLES:
            continue
        if not _defines_adapter(relative, state["files"][relative]):
            continue
        unit = _unit(relative, role, prefix)
        for line, module in imports:
            target = resolve(module, relative, state["root"], _language(relative))
            if not target or target not in roles:
                continue
            target_role, target_prefix = roles[target]
            if target_role not in ADAPTER_ROLES:
                continue
            if not _defines_adapter(target, state["files"][target]):
                continue
            if _unit(target, target_role, target_prefix) == unit:
                continue
            findings.append(
                _finding(
                    "adapter.imports-adapter",
                    "adapters",
                    "medium",
                    relative,
                    line,
                    "An adapter imports another adapter (`%s`). Adapters do not "
                    "know each other." % module,
                    "Connect them through a port or move the coordination to the "
                    "composition root.",
                )
            )
    return findings


def _adapter_classes(state, roles):
    classes = {}
    for relative, text in state["files"].items():
        if roles[relative][0] not in ADAPTER_ROLES:
            continue
        language = _language(relative)
        pattern = GO_STRUCT_RE if language == "go" else CLASS_RE
        for match in pattern.finditer(mask(text, language)):
            classes.setdefault(match.group(1), relative)
    return classes


def _instantiation_patterns(class_name, language):
    patterns = [r"\b%s\s*\(" % re.escape(class_name)]
    if language == "go":
        # A Go adapter is built with `driven.SQLOrders{}` or `NewSQLOrders()`.
        patterns.append(r"\b%s\s*\{" % re.escape(class_name))
        patterns.append(r"\bNew%s\s*\(" % re.escape(class_name))
    return [re.compile(pattern) for pattern in patterns]


def _check_instantiation(state, roles):
    classes = _adapter_classes(state, roles)
    findings = []
    for relative, text in state["files"].items():
        role = roles[relative][0]
        if role == "composition" or _is_test(relative):
            continue
        language = _language(relative)
        masked = mask(text, language)
        for class_name, definition in classes.items():
            if definition == relative:
                continue
            definition_role = roles[definition][0]
            # An adapter may build the objects of its own adapter folder. Only
            # the core, the ports and an adapter of the other family are
            # outside the boundary.
            if role in ADAPTER_ROLES and definition_role == role:
                continue
            for pattern in _instantiation_patterns(class_name, _language(definition)):
                for match in pattern.finditer(masked):
                    line = masked.count("\n", 0, match.start()) + 1
                    findings.append(
                        _finding(
                            "composition.instantiation-outside",
                            "composition root",
                            "medium",
                            relative,
                            line,
                            "The adapter `%s` is instantiated outside the "
                            "composition root." % class_name,
                            "Receive the port already built, or create the instance in "
                            "main, bootstrap or the container.",
                        )
                    )
    return findings


def _words(name):
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return {part.lower() for part in re.split(r"[^A-Za-z0-9]+", separated) if part}


def _declaration_line(text, words, pattern):
    for number, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line) and _words(line) & words:
            return number
    return 1


def _check_technological_port(state, roles):
    findings = []
    pattern = re.compile(r"\b(?:class|interface|type|protocol)\s+([A-Za-z_]\w*)")
    for relative, text in state["files"].items():
        if roles[relative][0] != "ports":
            continue
        stem = PurePosixPath(relative).stem
        technologies = _words(stem) & TECHNOLOGIES
        if technologies:
            line = _declaration_line(text, technologies, pattern)
        else:
            declarations = list(pattern.finditer(text))
            technologies = set()
            for declaration in declarations:
                if _words(declaration.group(1)) & TECHNOLOGIES:
                    technologies |= _words(declaration.group(1)) & TECHNOLOGIES
                    line = text.count("\n", 0, declaration.start()) + 1
                    break
            if not technologies:
                continue
        findings.append(
            _finding(
                "port.technology-name",
                "ports",
                "low",
                relative,
                line,
                "The port is named after a technology (%s). The name must say "
                "what the application needs, not what implements it."
                % ", ".join(sorted(technologies)),
                "Rename it by purpose, for example ForOrders or OrderRepository.",
            )
        )
    return findings


def _check_ports_contains_adapter(state, roles):
    findings = []
    for relative, text in state["files"].items():
        if roles[relative][0] != "ports":
            continue
        masked = mask(text, _language(relative))
        match = PORT_ADAPTER_RE.search(masked)
        named = "controller" in PurePosixPath(relative).stem.lower()
        if match is None and not named:
            continue
        if match is not None:
            line = masked.count("\n", 0, match.start()) + 1
            detail = "`%s`" % match.group(0).strip()
        else:
            line = 1
            detail = "its name contains `Controller`"
        findings.append(
            _finding(
                "ports.contains-adapter",
                "ports",
                "medium",
                relative,
                line,
                "A file under a ports folder looks like a driving adapter (%s)."
                % detail,
                "Move it to a driving adapters folder. A controller is an adapter "
                "that calls a driving port, not a port.",
            )
        )
    return findings


def _driven_port(relative, text):
    stem = PurePosixPath(relative).stem
    if "/driven/" in "/" + relative or "/out/" in "/" + relative:
        return True
    return bool(_words(stem) & DRIVEN_WORDS)


def _searchable(text):
    """Normalize for comparing names without case or separators."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _check_driven_port_without_double(state, roles):
    test_files = {
        relative: _searchable(text)
        for relative, text in state["files"].items()
        if _is_test(relative)
    }
    findings = []
    for relative, text in state["files"].items():
        if roles[relative][0] != "ports" or not _driven_port(relative, text):
            continue
        name = _searchable(PurePosixPath(relative).stem)
        has_double = any(
            name in content
            and any(marker in content for marker in DOUBLE_MARKERS)
            for content in test_files.values()
        )
        if has_double:
            continue
        findings.append(
            _finding(
                "tests.driven-port-without-double",
                "tests",
                "medium",
                relative,
                _declaration_line(
                    text,
                    _words(PurePosixPath(relative).stem),
                    re.compile(r"\b(?:class|interface|type|protocol)\s+([A-Za-z_]\w*)"),
                ),
                "The driven port `%s` has no in-memory double in tests."
                % PurePosixPath(relative).stem,
                "Add an in-memory double of the port and use it in the acceptance "
                "tests of the core.",
            )
        )
    return findings


def _check_core_tests(state, roles, extracted):
    core = [relative for relative in state["files"] if roles[relative][0] == "core"]
    if not core:
        return []
    isolated_tests = []
    for relative, text in state["files"].items():
        if not _is_test(relative):
            continue
        language = _language(relative)
        patterns = _forbidden(state["config"], language)
        isolated = True
        for line, module in extracted[relative]:
            if module.startswith("."):
                continue
            target = resolve(module, relative, state["root"], language)
            if target and roles.get(target, ("other", None))[0] in ADAPTER_ROLES:
                isolated = False
                break
            if any(_matches(module, pattern) for pattern in patterns):
                isolated = False
                break
        if isolated:
            isolated_tests.append(_searchable(mask(text, language)))
    for relative in core:
        stem = _searchable(PurePosixPath(relative).stem)
        if len(stem) < 3:
            continue
        # The name must appear in the code of an isolated test, not in a
        # comment or in an integration test that also mentions infrastructure.
        if any(stem in content for content in isolated_tests):
            return []
    return [
        _finding(
            "tests.core-without-tests",
            "tests",
            "medium",
            "",
            0,
            "No tests of the core isolated from infrastructure were found.",
            "Add unit tests of the core with in-memory doubles of the driven "
            "ports.",
        )
    ]


def _check_python_discovery(state):
    if state.get("pytest_config"):
        return []
    python = any(_language(relative) == "python" for relative in state["files"])
    if not python:
        return []
    candidates = [
        relative
        for relative in state["files"]
        if relative.startswith("tests/")
        and relative.endswith(".py")
        and PurePosixPath(relative).name.startswith("test_")
    ]
    if not candidates or "tests/__init__.py" in state["files"]:
        return []
    return [
        _finding(
            "tests.python-discovery",
            "tests",
            "low",
            "tests",
            0,
            "The tests folder has `test_*.py` files but no `__init__.py` and no "
            "pytest configuration. `python3 -m unittest` imports nothing and "
            "runs zero tests without failing.",
            "Add `tests/__init__.py`, or configure pytest and run it in CI so "
            "the test count is visible.",
        )
    ]


def _check_structure(state, roles):
    if state["config"] is not None:
        return []
    present = {role for role, _ in roles.values()}
    missing = []
    if "core" not in present:
        missing.append("core")
    if "ports" not in present:
        missing.append("ports")
    if not ({"driving", "driven", "adapters"} & present):
        missing.append("adapters")
    if not missing:
        return []
    proposal = {
        "core": ["src/domain", "src/application"],
        "ports": ["src/ports"],
        "driving_adapters": ["src/adapters/driving"],
        "driven_adapters": ["src/adapters/driven"],
        "composition_root": ["src/main.py"],
        "forbidden_in_core": [],
    }
    return [
        _finding(
            "structure.not-detected",
            "structure",
            "info",
            "",
            0,
            "The hexagonal structure could not be inferred: missing %s. Detection "
            "by folder names is a heuristic." % ", ".join(missing),
            "Create `.hexagonal.json` with the real paths, for example: %s"
            % json.dumps(proposal, ensure_ascii=False),
        )
    ]


def evaluate(state):
    roles = _classify_all(state)
    extracted = _extracted(state)
    findings = []
    findings += _check_core_imports_adapter(state, roles, extracted)
    findings += _check_core_library(state, roles, extracted)
    findings += _check_core_framework_annotation(state, roles)
    findings += _check_adapter_imports_adapter(state, roles, extracted)
    findings += _check_instantiation(state, roles)
    findings += _check_technological_port(state, roles)
    findings += _check_ports_contains_adapter(state, roles)
    findings += _check_driven_port_without_double(state, roles)
    findings += _check_core_tests(state, roles, extracted)
    findings += _check_python_discovery(state)
    findings += _check_structure(state, roles)
    return sorted(
        findings,
        key=lambda finding: (
            SEVERITY_ORDER[finding["severity"]],
            finding["file"],
            finding["line"],
            finding["id"],
        ),
    )


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


def audit_path(path, config_path=None):
    state = collect(path, config_path)
    findings = evaluate(state)
    summary = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        summary[finding["severity"]] += 1
    return {
        "path": state["root"],
        "config": "explicit" if state["config"] is not None else "inferred",
        "config_file": state["config_file"],
        "roles": {
            relative: role for relative, (role, _) in _classify_all(state).items()
        },
        "summary": summary,
        "findings": findings,
    }


def render_markdown(report):
    if report["config"] == "explicit":
        source = "explicit (`%s`)" % report.get("config_file")
    else:
        source = "inferred from folder names (no `.hexagonal.json`)"
    lines = [
        "# Hexagonal architecture audit",
        "",
        "- Path: `%s`" % report["path"],
        "- Configuration: %s" % source,
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("No findings.")
    for severity in SEVERITY_ORDER:
        group = [f for f in report["findings"] if f["severity"] == severity]
        if not group:
            continue
        lines += ["### %s (%d)" % (severity.capitalize(), len(group)), ""]
        for finding in group:
            location = finding["file"] or "repository"
            if finding["line"]:
                location += ":%d" % finding["line"]
            lines.append(
                "- **[%s] %s** (%s) `%s`: %s"
                % (
                    finding["severity"],
                    finding["id"],
                    finding["area"],
                    location,
                    finding["message"],
                )
            )
            lines.append("  - Fix: %s" % finding["fix"])
        lines.append("")
    summary = report["summary"]
    lines += [
        "## Summary",
        "",
        "| Severity | Findings |",
        "| --- | --- |",
    ]
    lines += [
        "| %s | %d |" % (severity.capitalize(), summary[severity])
        for severity in SEVERITY_ORDER
    ]
    lines += [
        "",
        "Folder inference is a heuristic: if it does not match the real "
        "structure, write `.hexagonal.json`.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit a repo against hexagonal architecture (read-only)."
    )
    parser.add_argument("--path", default=".", help="root of the repo to audit")
    parser.add_argument(
        "--config",
        default=None,
        help="path to .hexagonal.json; searched at the root by default",
    )
    parser.add_argument("--json", action="store_true", help="dump the report as JSON")
    args = parser.parse_args(argv)

    try:
        report = audit_path(args.path, args.config)
    except FileNotFoundError:
        print("error: path %s does not exist" % args.path, file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
