import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "hexagonal-architecture" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import imports  # noqa: E402


def tree(base, files):
    """Create a temporary tree and return the resolved root."""
    for relative, text in files.items():
        target = Path(base) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return str(base)


class ExtractPythonTest(unittest.TestCase):
    def test_absolute_and_relative_imports_with_line(self):
        text = (
            "import os\n"
            "import sqlalchemy.orm as orm\n"
            "from .ports import repo\n"
            "from ..domain.model import Order\n"
        )
        self.assertEqual(
            imports.extract_imports(text, "python"),
            [
                (1, "os"),
                (2, "sqlalchemy.orm"),
                (3, ".ports"),
                (4, "..domain.model"),
            ],
        )

    def test_trailing_comment_does_not_become_part_of_the_module(self):
        text = "import sqlalchemy  # noqa\n"
        self.assertEqual(imports.extract_imports(text, "python"), [(1, "sqlalchemy")])

    def test_docstring_that_looks_like_an_import_is_ignored(self):
        text = (
            '"""\n'
            "import requests\n"
            '"""\n'
            "import os\n"
        )
        self.assertEqual(imports.extract_imports(text, "python"), [(4, "os")])

    def test_semicolon_separated_imports_are_each_extracted(self):
        text = "import sqlalchemy; import requests\nimport os\n"
        self.assertEqual(
            imports.extract_imports(text, "python"),
            [(1, "sqlalchemy"), (1, "requests"), (2, "os")],
        )

    def test_statement_after_a_semicolon_is_not_taken_for_a_module(self):
        self.assertEqual(
            imports.extract_imports("import os; x = 1\n", "python"),
            [(1, "os")],
        )


class ExtractTypeScriptTest(unittest.TestCase):
    def test_default_multiline_require_side_effect_and_export(self):
        text = (
            "import express from 'express';\n"
            "import {\n"
            "  SqlRepo,\n"
            "} from './sql-repo';\n"
            "const pg = require('pg');\n"
            "import './side-effect';\n"
            "export { Order } from '../domain/order';\n"
            "const lazy = await import('./lazy');\n"
        )
        self.assertEqual(
            imports.extract_imports(text, "ts"),
            [
                (1, "express"),
                (4, "./sql-repo"),
                (5, "pg"),
                (6, "./side-effect"),
                (7, "../domain/order"),
                (8, "./lazy"),
            ],
        )

    def test_comments_and_strings_that_look_like_imports_are_ignored(self):
        text = (
            "// import { Pool } from 'pg';\n"
            "const sample = \"from 'pg'\";\n"
            "import { Order } from './order';\n"
        )
        self.assertEqual(imports.extract_imports(text, "ts"), [(3, "./order")])


class ExtractJavaKotlinTest(unittest.TestCase):
    def test_java_and_kotlin_imports(self):
        java = (
            "package com.acme.domain;\n"
            "import com.acme.domain.Order;\n"
            "import static java.util.List.of;\n"
            "import org.springframework.web.bind.annotation.RestController;\n"
        )
        self.assertEqual(
            imports.extract_imports(java, "java"),
            [
                (2, "com.acme.domain.Order"),
                (3, "java.util.List.of"),
                (4, "org.springframework.web.bind.annotation.RestController"),
            ],
        )
        kotlin = "package com.acme\nimport java.sql.Connection\nimport com.acme.ports.*\n"
        self.assertEqual(
            imports.extract_imports(kotlin, "kotlin"),
            [(2, "java.sql.Connection"), (3, "com.acme.ports.*")],
        )

    def test_block_comment_that_looks_like_an_import_is_ignored(self):
        text = (
            "package com.acme.domain;\n"
            "/*\n"
            "import java.sql.Connection;\n"
            "*/\n"
            "import com.acme.ports.ForOrders;\n"
        )
        self.assertEqual(
            imports.extract_imports(text, "java"),
            [(5, "com.acme.ports.ForOrders")],
        )


class ExtractGoTest(unittest.TestCase):
    def test_block_and_single(self):
        text = (
            "package main\n"
            "\n"
            "import (\n"
            '\t"fmt"\n'
            '\t"database/sql"\n'
            '\talias "github.com/acme/app/domain"\n'
            ")\n"
            "\n"
            'import "net/http"\n'
        )
        self.assertEqual(
            imports.extract_imports(text, "go"),
            [
                (4, "fmt"),
                (5, "database/sql"),
                (6, "github.com/acme/app/domain"),
                (9, "net/http"),
            ],
        )

    def test_raw_string_imports_are_extracted(self):
        text = (
            "package main\n"
            "\n"
            "import (\n"
            '\t"fmt"\n'
            "\t`github.com/lib/pq`\n"
            ")\n"
            "\n"
            "import `github.com/redis/go-redis/v9`\n"
        )
        self.assertEqual(
            imports.extract_imports(text, "go"),
            [
                (4, "fmt"),
                (5, "github.com/lib/pq"),
                (8, "github.com/redis/go-redis/v9"),
            ],
        )


class ResolveTypeScriptTest(unittest.TestCase):
    def test_relative_with_extension_and_index_and_external_package(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "src/app/main.ts": "import { Order } from '../domain';\n",
                    "src/domain/index.ts": "export class Order {}\n",
                    "src/app/services/order.ts": "export class OrderService {}\n",
                },
            )
            self.assertEqual(
                imports.resolve("./services/order", "src/app/main.ts", base, "ts"),
                "src/app/services/order.ts",
            )
            self.assertEqual(
                imports.resolve("../domain", "src/app/main.ts", base, "ts"),
                "src/domain/index.ts",
            )
            self.assertIsNone(
                imports.resolve("express", "src/app/main.ts", base, "ts")
            )

    def test_esm_js_import_resolves_to_the_ts_source(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "src/core/place.ts": "import { Order } from './order.js';\n",
                    "src/core/order.ts": "export class Order {}\n",
                },
            )
            self.assertEqual(
                imports.resolve("./order.js", "src/core/place.ts", base, "ts"),
                "src/core/order.ts",
            )


class ResolvePythonTest(unittest.TestCase):
    def test_relative_with_dots_and_absolute_under_root_and_src(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "src/pkg/app/service.py": "from ..domain.model import Order\n",
                    "src/pkg/domain/model.py": "class Order: pass\n",
                    "domain/model.py": "class Order: pass\n",
                    "src/core/entity.py": "class Entity: pass\n",
                },
            )
            self.assertEqual(
                imports.resolve(
                    "..domain.model", "src/pkg/app/service.py", base, "python"
                ),
                "src/pkg/domain/model.py",
            )
            self.assertEqual(
                imports.resolve("domain.model", "src/pkg/app/service.py", base, "python"),
                "domain/model.py",
            )
            self.assertEqual(
                imports.resolve("core.entity", "src/pkg/app/service.py", base, "python"),
                "src/core/entity.py",
            )
            self.assertIsNone(
                imports.resolve("sqlalchemy.orm", "src/pkg/app/service.py", base, "python")
            )


class ResolveJavaGoTest(unittest.TestCase):
    def test_java_by_package_suffix(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "src/main/java/com/acme/domain/Order.java": "package com.acme.domain;\n",
                    "src/main/java/com/acme/adapters/SqlRepo.java": "package com.acme.adapters;\n",
                },
            )
            self.assertEqual(
                imports.resolve(
                    "com.acme.domain.Order",
                    "src/main/java/com/acme/adapters/SqlRepo.java",
                    base,
                    "java",
                ),
                "src/main/java/com/acme/domain/Order.java",
            )

    def test_java_wildcard_resolves_to_the_package(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "src/main/java/com/acme/adapters/driven/SqlRepo.java": (
                        "package com.acme.adapters.driven;\n"
                    ),
                },
            )
            self.assertEqual(
                imports.resolve(
                    "com.acme.adapters.driven.*",
                    "src/main/java/com/acme/domain/Order.java",
                    base,
                    "java",
                ),
                "src/main/java/com/acme/adapters/driven/SqlRepo.java",
            )

    def test_go_by_package_suffix(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "internal/domain/order.go": "package domain\n",
                    "cmd/api/main.go": 'import "github.com/acme/app/internal/domain"\n',
                },
            )
            self.assertEqual(
                imports.resolve(
                    "github.com/acme/app/internal/domain",
                    "cmd/api/main.go",
                    base,
                    "go",
                ),
                "internal/domain/order.go",
            )

    def test_go_module_path_makes_external_imports_unresolvable(self):
        with tempfile.TemporaryDirectory() as base:
            tree(
                base,
                {
                    "go.mod": "module example.com/app\n\ngo 1.25\n",
                    "internal/adapters/driving/http/main.go": "package http\n",
                    "internal/domain/order.go": "package domain\n",
                },
            )
            self.assertEqual(
                imports.resolve(
                    "example.com/app/internal/domain",
                    "internal/domain/order.go",
                    base,
                    "go",
                ),
                "internal/domain/order.go",
            )
            self.assertIsNone(
                imports.resolve(
                    "github.com/other/http",
                    "internal/domain/order.go",
                    base,
                    "go",
                )
            )


if __name__ == "__main__":
    unittest.main()
