#!/usr/bin/env python3
"""Import extraction and resolution, unaware of the architecture.

These functions decide nothing about roles or rules: they only turn text into
(line, module) pairs and modules into repository paths. The audit builds on
them, so the rules can be tested with plain text.

Resolution reads the disk because a relative import can only be resolved by
knowing which files exist. The index is cached per root because the CLI is
single use and auditing a large tree with one walk per import would be
quadratic.

Internal use of `scripts/audit.py`.
"""

import os
import re
from pathlib import Path

# Same directories the audit ignores: they are not code of the repo.
IGNORED = {
    "node_modules",
    ".git",
    "venv",
    ".venv",
    "dist",
    "build",
    "target",
    "vendor",
    "__pycache__",
}

EXTENSIONS = {
    "python": {".py"},
    "ts": {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"},
    "java": {".java", ".kt"},
    "go": {".go"},
}
EXTENSIONS["js"] = EXTENSIONS["ts"]
EXTENSIONS["kotlin"] = EXTENSIONS["java"]

_LANGUAGES = {
    "python": "python",
    "py": "python",
    "ts": "ts",
    "tsx": "ts",
    "js": "ts",
    "jsx": "ts",
    "javascript": "ts",
    "typescript": "ts",
    "java": "java",
    "kotlin": "java",
    "kt": "java",
    "go": "go",
    "golang": "go",
}

_PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_PY_FROM = re.compile(
    r"^[ \t]*from[ \t]+(\.*[\w.]*)[ \t]+import\b", re.MULTILINE
)

_FROM = re.compile(r"""\bfrom\s*['"]([^'"]+)['"]""")
_IMPORT_ONLY = re.compile(r"""^[ \t]*import[ \t]*['"]([^'"]+)['"]""", re.MULTILINE)
_REQUIRE = re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_DYNAMIC_IMPORT = re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)""")

_JAVA_IMPORT = re.compile(
    r"^[ \t]*import[ \t]+(?:static[ \t]+)?([\w.]*[\w](?:\.\*)?)[ \t]*;?",
    re.MULTILINE,
)

_GO_BLOCK = re.compile(r"^[ \t]*import[ \t]*\([ \t]*$")
_GO_END = re.compile(r"^[ \t]*\)[ \t]*$")
_GO_SINGLE = re.compile(r'^[ \t]*import[ \t]+(?:[\w.]+[ \t]+)?["`]([^"`]+)["`]')
_GO_ENTRY = re.compile(r'(?:[\w.]+[ \t]+)?["`]([^"`]+)["`]')


def _language(lang):
    return _LANGUAGES.get((lang or "").lower())


def _line(text, position):
    return text.count("\n", 0, position) + 1


def _blank(chars, start, end):
    for position in range(start, min(end, len(chars))):
        if chars[position] != "\n":
            chars[position] = " "


def mask(text, language, blank_strings=True):
    """Blank comments and optionally string literals, keeping offsets and lines.

    String literals are always scanned so a comment marker inside one is not
    taken for a comment; they are replaced only when `blank_strings` is true.
    Python docstrings are strings too. Block comments exist in every language
    except Python.
    """
    chars = list(text)
    size = len(text)
    line_marker = "#" if language == "python" else "//"
    index = 0
    while index < size:
        if text.startswith(line_marker, index):
            end = text.find("\n", index)
            end = size if end == -1 else end
            _blank(chars, index, end)
            index = end
            continue
        if language != "python" and text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = size if end == -1 else end + 2
            _blank(chars, index, end)
            index = end
            continue
        if language == "python" and text.startswith(('"""', "'''"), index):
            quote = text[index : index + 3]
            end = text.find(quote, index + 3)
            end = size if end == -1 else end + 3
            if blank_strings:
                _blank(chars, index, end)
            index = end
            continue
        char = text[index]
        if char in ('"', "'", "`"):
            end = index + 1
            while end < size:
                if text[end] == "\\":
                    end += 2
                    continue
                if text[end] == char:
                    end += 1
                    break
                if text[end] == "\n" and char != "`":
                    break
                end += 1
            if blank_strings:
                _blank(chars, index, end)
            index = end
            continue
        index += 1
    return "".join(chars)


def _inside_string(commentless, stringless, start):
    """Whether the first non-blank character of a match sits in a string."""
    position = start
    while position < len(commentless) and commentless[position] in " \t":
        position += 1
    return (
        position < len(commentless)
        and commentless[position] != stringless[position]
    )


def extract_imports(text, lang):
    """Return [(line, module)] sorted by appearance in the file.

    Matching runs on masked text: comments never produce an import, and a
    docstring or a string literal that looks like an import is ignored. The
    string literals that hold a real specifier stay readable for TypeScript,
    which is why that language masks comments and strings separately.
    """
    language = _language(lang)
    if language == "python":
        masked = mask(text, language)
        found = []
        for match in _PY_IMPORT.finditer(masked):
            # `import a; import b` is one line with two statements.
            for index, statement in enumerate(match.group(1).split(";")):
                statement = statement.strip()
                if index:
                    if not statement.startswith("import "):
                        continue
                    statement = statement[len("import ") :]
                for chunk in statement.split(","):
                    module = chunk.strip().split(" as ")[0].strip()
                    if module:
                        found.append((_line(masked, match.start()), module))
        for match in _PY_FROM.finditer(masked):
            module = match.group(1).strip()
            if module:
                found.append((_line(masked, match.start()), module))
        return sorted(found, key=lambda pair: pair[0])

    if language == "ts":
        commentless = mask(text, language, blank_strings=False)
        stringless = mask(text, language, blank_strings=True)
        found = []
        for pattern in (_FROM, _IMPORT_ONLY, _REQUIRE, _DYNAMIC_IMPORT):
            for match in pattern.finditer(commentless):
                if _inside_string(commentless, stringless, match.start()):
                    continue
                found.append((_line(commentless, match.start()), match.group(1)))
        # The same import can match more than one pattern only with unusual
        # syntax; deduplicating avoids counting the same line twice.
        seen = set()
        clean = []
        for pair in sorted(found, key=lambda pair: pair[0]):
            if pair not in seen:
                seen.add(pair)
                clean.append(pair)
        return clean

    if language == "java":
        masked = mask(text, language)
        found = []
        for match in _JAVA_IMPORT.finditer(masked):
            module = match.group(1)
            # Keep the wildcard marker: the resolver needs it to tell a
            # package import from a class import.
            if not module.endswith(".*"):
                module = module.rstrip(".")
            if module:
                found.append((_line(masked, match.start()), module))
        return found

    if language == "go":
        # Go import paths live in string literals, so only comments are
        # masked here.
        commentless = mask(text, language, blank_strings=False)
        found = []
        in_block = False
        for number, line in enumerate(commentless.splitlines(), start=1):
            if _GO_BLOCK.match(line):
                in_block = True
                continue
            if in_block:
                if _GO_END.match(line):
                    in_block = False
                    continue
                entry = _GO_ENTRY.search(line)
                if entry:
                    found.append((number, entry.group(1)))
                continue
            single = _GO_SINGLE.match(line)
            if single:
                found.append((number, single.group(1)))
        return found

    return []


_INDEXES = {}


def _index(root, extensions):
    key = (str(Path(root).resolve()), tuple(sorted(extensions)))
    if key not in _INDEXES:
        files = []
        base = Path(root)
        for directory, subdirectories, names in os.walk(base):
            subdirectories[:] = [
                name for name in subdirectories if name not in IGNORED
            ]
            for name in names:
                if Path(name).suffix in extensions:
                    path = Path(directory) / name
                    files.append(path.relative_to(base).as_posix())
        _INDEXES[key] = sorted(files)
    return _INDEXES[key]


def _relative(root, path):
    try:
        relative = Path(path).resolve().relative_to(Path(root).resolve())
    except ValueError:
        return None
    return relative.as_posix()


def _exists(root, path):
    return Path(path).is_file() and _relative(root, path) is not None


_TS_EMITTED = {
    ".js": (".ts", ".tsx"),
    ".jsx": (".tsx",),
    ".mjs": (".mts",),
    ".cjs": (".cts",),
}


def _resolve_relative_ts(module, from_file, root):
    if module not in (".", "..") and not module.startswith(("./", "../")):
        return None
    base = (Path(root) / from_file).parent / module
    candidates = [base] if base.suffix else []
    if base.suffix in _TS_EMITTED:
        # An ESM import names the emitted file (`./order.js`), but the source
        # is `order.ts`.
        stem = base.with_suffix("")
        candidates += [stem.with_suffix(ext) for ext in _TS_EMITTED[base.suffix]]
    candidates += [base.with_name(base.name + ext) for ext in EXTENSIONS["ts"]]
    candidates += [
        base / ("index" + ext) for ext in EXTENSIONS["ts"]
    ]
    for candidate in candidates:
        if _exists(root, candidate):
            return _relative(root, candidate)
    return None


def _resolve_python(module, from_file, root):
    if module.startswith("."):
        dots = len(module) - len(module.lstrip("."))
        rest = module[dots:]
        base = (Path(root) / from_file).parent
        for _ in range(dots - 1):
            base = base.parent
        candidate = base / rest.replace(".", "/") if rest else base
        options = [candidate.with_suffix(".py"), candidate / "__init__.py"]
    else:
        parts = module.split(".")
        options = []
        for prefix in (Path(root), Path(root) / "src"):
            candidate = prefix.joinpath(*parts)
            options += [candidate.with_suffix(".py"), candidate / "__init__.py"]
    for option in options:
        if _exists(root, option):
            return _relative(root, option)
    return None


def _resolve_java(module, root):
    wildcard = module.endswith(".*")
    parts = (module[:-2] if wildcard else module).split(".")
    files = _index(root, EXTENSIONS["java"])
    if wildcard:
        # The import names a package, so any class in it is a valid target.
        for relative in files:
            folders = relative.split("/")[:-1]
            if len(folders) >= len(parts) and folders[-len(parts):] == parts:
                return relative
        return None
    # Try the full name and then every suffix: repos usually have a folder
    # prefix (src/main/java) that the package does not repeat.
    for start in range(len(parts)):
        suffix = parts[start:]
        class_name = suffix[-1]
        package = suffix[:-1]
        for relative in files:
            chunks = relative.split("/")
            if chunks[-1].rsplit(".", 1)[0] != class_name:
                continue
            folders = chunks[:-1]
            if len(folders) >= len(package) and folders[-len(package):] == package:
                return relative
    return None


_MODULE_CACHE = {}


def _go_module(root):
    """Module path from go.mod, or None when the repo has no go.mod."""
    key = str(Path(root).resolve())
    if key not in _MODULE_CACHE:
        module = None
        try:
            for line in (Path(root) / "go.mod").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                match = re.match(r"\s*module\s+(\S+)", line)
                if match:
                    module = match.group(1).strip('"')
                    break
        except OSError:
            pass
        _MODULE_CACHE[key] = module
    return _MODULE_CACHE[key]


def _resolve_go(module, root):
    parts = module.split("/")
    files = _index(root, EXTENSIONS["go"])
    directories = {}
    for relative in files:
        directory = relative.rsplit("/", 1)[0] if "/" in relative else ""
        directories.setdefault(directory, []).append(relative)
    go_module = _go_module(root)
    if go_module:
        # With go.mod the module path is authoritative: an import outside it
        # is external even when a local folder shares its last component.
        if module == go_module:
            relative_dir = ""
        elif module.startswith(go_module + "/"):
            relative_dir = module[len(go_module) + 1 :]
        else:
            return None
        for directory, contents in sorted(directories.items()):
            if directory == relative_dir or directory.endswith("/" + relative_dir):
                return sorted(contents)[0]
        return None
    for start in range(len(parts)):
        suffix = parts[start:]
        for directory, contents in sorted(directories.items()):
            folders = directory.split("/") if directory else []
            if len(folders) >= len(suffix) and folders[-len(suffix):] == suffix:
                return sorted(contents)[0]
    return None


def resolve(module, from_file, root, lang):
    """Path relative to `root` for the imported module, or None if external."""
    language = _language(lang)
    if not module:
        return None
    if language == "ts":
        return _resolve_relative_ts(module, from_file, root)
    if language == "python":
        return _resolve_python(module, from_file, root)
    if language == "java":
        return _resolve_java(module, root)
    if language == "go":
        return _resolve_go(module, root)
    return None
