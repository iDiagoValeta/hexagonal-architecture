import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "hexagonal-architecture" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import audit  # noqa: E402


def tree(base, files):
    for relative, text in files.items():
        target = Path(base) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def audit_tree(files, config=None):
    with tempfile.TemporaryDirectory() as base:
        tree(base, files)
        if config is not None:
            (Path(base) / ".hexagonal.json").write_text(
                json.dumps(config), encoding="utf-8"
            )
        return audit.audit_path(base)


def with_severity(report, severity):
    return [
        (finding["id"], finding["file"], finding["line"])
        for finding in report["findings"]
        if finding["severity"] == severity
    ]


def ids(report, severity):
    return [
        finding["id"]
        for finding in report["findings"]
        if finding["severity"] == severity
    ]


class CleanTreesTest(unittest.TestCase):
    """One clean case per language: the core carries no technology."""

    def test_python_without_high_findings(self):
        report = audit_tree(
            {
                "src/domain/order.py": (
                    "from dataclasses import dataclass\n"
                    "\n"
                    "@dataclass\n"
                    "class Order:\n"
                    "    id: str\n"
                ),
                "src/ports/orders.py": (
                    "from typing import Protocol\n"
                    "\n"
                    "class ForOrders(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
                "src/adapters/driven/sql_repo.py": (
                    "from src.domain.order import Order\n"
                    "\n"
                    "class SqlRepo:\n"
                    "    def save(self, order: Order): ...\n"
                ),
                "src/adapters/driving/http_api.py": (
                    "from src.ports.orders import ForOrders\n"
                    "\n"
                    "class HttpApi:\n"
                    "    def __init__(self, port: ForOrders):\n"
                    "        self.port = port\n"
                ),
                "src/main.py": (
                    "from src.adapters.driven.sql_repo import SqlRepo\n"
                    "\n"
                    "repo = SqlRepo()\n"
                ),
                "tests/test_orders.py": (
                    "from src.ports.orders import ForOrders\n"
                    "\n"
                    "class InMemoryOrders:\n"
                    "    pass\n"
                ),
            }
        )
        self.assertEqual(with_severity(report, "high"), [])

    def test_typescript_without_high_findings(self):
        report = audit_tree(
            {
                "src/domain/order.ts": "export class Order {}\n",
                "src/ports/orders.ts": "export interface ForOrders { save(order: unknown): void }\n",
                "src/adapters/driven/sql-repo.ts": (
                    "import { Order } from '../../domain/order';\n"
                    "export class SqlRepo { save(order: Order) {} }\n"
                ),
                "src/adapters/driving/http.ts": (
                    "import { ForOrders } from '../../ports/orders';\n"
                    "export class HttpApi { constructor(private port: ForOrders) {} }\n"
                ),
                "src/main.ts": (
                    "import { SqlRepo } from './adapters/driven/sql-repo';\n"
                    "const repo = new SqlRepo();\n"
                ),
                "tests/orders.test.ts": (
                    "import { ForOrders } from '../src/ports/orders';\n"
                    "class InMemoryOrders implements ForOrders { save() {} }\n"
                ),
            }
        )
        self.assertEqual(with_severity(report, "high"), [])

    def test_java_without_high_findings(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/domain/Order.java": (
                    "package com.acme.domain;\n"
                    "public class Order {}\n"
                ),
                "src/main/java/com/acme/ports/ForOrders.java": (
                    "package com.acme.ports;\n"
                    "public interface ForOrders {}\n"
                ),
                "src/main/java/com/acme/adapters/driven/SqlRepo.java": (
                    "package com.acme.adapters.driven;\n"
                    "import com.acme.ports.ForOrders;\n"
                    "public class SqlRepo implements ForOrders {}\n"
                ),
                "src/main/java/com/acme/adapters/driving/Api.java": (
                    "package com.acme.adapters.driving;\n"
                    "import com.acme.ports.ForOrders;\n"
                    "public class Api {}\n"
                ),
                "src/main/java/com/acme/Main.java": (
                    "package com.acme;\n"
                    "import com.acme.adapters.driven.SqlRepo;\n"
                    "public class Main { SqlRepo repo = new SqlRepo(); }\n"
                ),
                "tests/java/com/acme/InMemoryOrdersTest.java": (
                    "package com.acme;\n"
                    "public class InMemoryOrdersTest {}\n"
                ),
            }
        )
        self.assertEqual(with_severity(report, "high"), [])

    def test_go_without_high_findings(self):
        report = audit_tree(
            {
                "internal/domain/order.go": "package domain\n\ntype Order struct{}\n",
                "internal/ports/orders.go": (
                    "package ports\n\ntype ForOrders interface { Save(Order) }\n"
                ),
                "internal/adapters/driven/sql_repo.go": (
                    "package driven\n"
                    'import "github.com/acme/app/internal/ports"\n'
                    "type SqlRepo struct{}\n"
                    "var _ ports.ForOrders = SqlRepo{}\n"
                ),
                "internal/adapters/driving/http.go": (
                    "package driving\n"
                    'import "github.com/acme/app/internal/ports"\n'
                    "type HttpApi struct{}\n"
                    "var _ ports.ForOrders = HttpApi{}\n"
                ),
                "cmd/main.go": (
                    "package main\n"
                    'import "github.com/acme/app/internal/adapters/driven"\n'
                    "func main() { _ = driven.SqlRepo{} }\n"
                ),
                "tests/in_memory.go": (
                    "package tests\n"
                    'import "github.com/acme/app/internal/ports"\n'
                    "type InMemoryOrders struct{}\n"
                    "var _ ports.ForOrders = InMemoryOrders{}\n"
                ),
            }
        )
        self.assertEqual(with_severity(report, "high"), [])


class DirtyCoreTest(unittest.TestCase):
    """The core imports an ORM and an adapter: two high findings with file and line."""

    def test_python(self):
        report = audit_tree(
            {
                "src/domain/order.py": (
                    "from sqlalchemy.orm import Session\n"
                    "from adapters.driven.sql_repo import SqlRepo\n"
                    "class Order:\n"
                    "    pass\n"
                ),
                "src/adapters/driven/sql_repo.py": (
                    "class SqlRepo:\n"
                    "    pass\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "src/domain/order.py", 1),
                ("core.imports-adapter", "src/domain/order.py", 2),
            ],
        )

    def test_typescript(self):
        report = audit_tree(
            {
                "src/domain/order.ts": (
                    "import { PrismaClient } from '@prisma/client';\n"
                    "import { SqlRepo } from '../adapters/driven/sql-repo';\n"
                    "export class Order {}\n"
                ),
                "src/adapters/driven/sql-repo.ts": "export class SqlRepo {}\n",
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "src/domain/order.ts", 1),
                ("core.imports-adapter", "src/domain/order.ts", 2),
            ],
        )

    def test_java(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/domain/Order.java": (
                    "package com.acme.domain;\n"
                    "import org.springframework.web.client.RestTemplate;\n"
                    "import com.acme.adapters.driven.SqlRepo;\n"
                    "public class Order {}\n"
                ),
                "src/main/java/com/acme/adapters/driven/SqlRepo.java": (
                    "package com.acme.adapters.driven;\n"
                    "public class SqlRepo {}\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "src/main/java/com/acme/domain/Order.java", 2),
                ("core.imports-adapter", "src/main/java/com/acme/domain/Order.java", 3),
            ],
        )

    def test_java_http_client_and_wildcard_adapter(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/domain/Order.java": (
                    "package com.acme.domain;\n"
                    "import java.net.http.HttpClient;\n"
                    "import org.springframework.stereotype.Service;\n"
                    "import com.acme.adapters.driven.*;\n"
                    "public class Order {}\n"
                ),
                "src/main/java/com/acme/adapters/driven/SqlRepo.java": (
                    "package com.acme.adapters.driven;\n"
                    "public class SqlRepo {}\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "src/main/java/com/acme/domain/Order.java", 2),
                ("core.forbidden-library", "src/main/java/com/acme/domain/Order.java", 3),
                ("core.imports-adapter", "src/main/java/com/acme/domain/Order.java", 4),
            ],
        )

    def test_go(self):
        report = audit_tree(
            {
                "internal/domain/order.go": (
                    "package domain\n"
                    "\n"
                    "import (\n"
                    '\t"database/sql"\n'
                    '\t"github.com/acme/app/internal/adapters/driven"\n'
                    ")\n"
                    "\n"
                    "type Order struct{}\n"
                ),
                "internal/adapters/driven/sql_repo.go": (
                    "package driven\n"
                    "type SqlRepo struct{}\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "internal/domain/order.go", 4),
                ("core.imports-adapter", "internal/domain/order.go", 5),
            ],
        )

    def test_go_vendor_outside_the_go_arch_lint_allow_list_is_high(self):
        report = audit_tree(
            {
                "internal/domain/order.go": (
                    "package domain\n"
                    'import "github.com/lib/pq"\n'
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [("core.forbidden-library", "internal/domain/order.go", 2)],
        )


class FrameworkAnnotationTest(unittest.TestCase):
    def test_spring_annotation_in_core_is_high_and_skips_comments_and_strings(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/domain/OrderService.java": (
                    "package com.acme.domain;\n"
                    "public class OrderService {\n"
                    "    // @Service belongs in an adapter, not here\n"
                    '    String sample = "@Entity";\n'
                    "    @Transactional\n"
                    "    void save() {}\n"
                    "}\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [("core.framework-annotation", "src/main/java/com/acme/domain/OrderService.java", 5)],
        )

    def test_plain_java_core_has_no_framework_annotation(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/domain/Order.java": (
                    "package com.acme.domain;\n"
                    "public class Order {\n"
                    "    @Override\n"
                    "    public String toString() { return \"@Service\"; }\n"
                    "}\n"
                ),
            }
        )
        self.assertNotIn("core.framework-annotation", ids(report, "high"))

    def test_fastapi_decorator_in_core_is_high_and_keeps_the_import_finding(self):
        report = audit_tree(
            {
                "src/domain/order_api.py": (
                    "from fastapi import FastAPI\n"
                    "app = FastAPI()\n"
                    '@app.get("/orders")\n'
                    "def list_orders():\n"
                    "    return []\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "high"),
            [
                ("core.forbidden-library", "src/domain/order_api.py", 1),
                ("core.framework-annotation", "src/domain/order_api.py", 3),
            ],
        )

    def test_standard_decorators_in_python_core_are_quiet(self):
        report = audit_tree(
            {
                "src/domain/order.py": (
                    "from dataclasses import dataclass\n"
                    "\n"
                    "@dataclass\n"
                    "class Order:\n"
                    "    @property\n"
                    "    def total(self):\n"
                    "        return 0\n"
                ),
            }
        )
        self.assertNotIn("core.framework-annotation", ids(report, "high"))


class PortsContainsAdapterTest(unittest.TestCase):
    def test_controller_under_ports_is_medium(self):
        report = audit_tree(
            {
                "src/ports/OrderController.java": (
                    "package com.acme.ports;\n"
                    "@RestController\n"
                    "public class OrderController {}\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "medium"),
            [("ports.contains-adapter", "src/ports/OrderController.java", 2)],
        )

    def test_express_route_under_ports_is_medium(self):
        report = audit_tree(
            {
                "src/ports/orders_api.js": (
                    "const express = require('express');\n"
                    "const router = express.Router();\n"
                    "router.get('/orders', handler);\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "medium"),
            [("ports.contains-adapter", "src/ports/orders_api.js", 3)],
        )

    def test_plain_port_is_quiet(self):
        report = audit_tree(
            {
                "src/ports/orders.py": (
                    "from typing import Protocol\n"
                    "class ForOrders(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
            }
        )
        self.assertNotIn("ports.contains-adapter", ids(report, "medium"))


class AdaptersTest(unittest.TestCase):
    def test_adapter_imports_another_adapter(self):
        report = audit_tree(
            {
                "src/adapters/driven/sql_repo.py": (
                    "from src.adapters.driving.api import Api\n"
                    "class SqlRepo:\n"
                    "    pass\n"
                ),
                "src/adapters/driving/api.py": "class Api:\n    pass\n",
            }
        )
        self.assertEqual(
            with_severity(report, "medium"),
            [("adapter.imports-adapter", "src/adapters/driven/sql_repo.py", 1)],
        )

    def test_flat_adapters_folder_is_recognized(self):
        report = audit_tree(
            {
                "src/domain/order.py": (
                    "from src.adapters import SqlRepo\n"
                    "class Order:\n"
                    "    pass\n"
                ),
                "src/adapters/__init__.py": (
                    "from src.adapters.sql_repo import SqlRepo\n"
                ),
                "src/adapters/sql_repo.py": "class SqlRepo:\n    pass\n",
            }
        )
        self.assertEqual(report["roles"]["src/adapters/sql_repo.py"], "adapters")
        self.assertEqual(
            with_severity(report, "high"),
            [("core.imports-adapter", "src/domain/order.py", 1)],
        )

    def test_two_adapters_of_the_same_flat_family_do_not_import_each_other(self):
        report = audit_tree(
            {
                "src/adapters/driven/sql_repo.py": (
                    "from src.adapters.driven.in_memory_repository import "
                    "InMemoryOrderRepository\n"
                    "class SqlRepo:\n"
                    "    pass\n"
                ),
                "src/adapters/driven/in_memory_repository.py": (
                    "class InMemoryOrderRepository:\n"
                    "    pass\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "medium"),
            [
                (
                    "adapter.imports-adapter",
                    "src/adapters/driven/sql_repo.py",
                    1,
                )
            ],
        )

    def test_canonical_in_memory_orders_adapter_is_recognized(self):
        report = audit_tree(
            {
                "src/adapters/driven/sql_orders_repository.py": (
                    "from src.adapters.driven.in_memory_orders import "
                    "InMemoryOrders\n"
                    "class SqlOrdersRepository:\n"
                    "    pass\n"
                ),
                "src/adapters/driven/in_memory_orders.py": (
                    "class InMemoryOrders:\n"
                    "    pass\n"
                ),
            }
        )
        self.assertEqual(
            with_severity(report, "medium"),
            [
                (
                    "adapter.imports-adapter",
                    "src/adapters/driven/sql_orders_repository.py",
                    1,
                )
            ],
        )

    def test_instantiation_inside_an_adapter_folder_is_not_a_violation(self):
        report = audit_tree(
            {
                "src/orders/adapters/driven/order_row.py": (
                    "class OrderRow:\n"
                    "    pass\n"
                ),
                "src/orders/adapters/driven/sql_order_repository.py": (
                    "from src.orders.adapters.driven.order_row import OrderRow\n"
                    "class SqlOrderRepository:\n"
                    "    def save(self):\n"
                    "        return OrderRow()\n"
                ),
                "src/orders/main.py": (
                    "from src.orders.adapters.driven.sql_order_repository import "
                    "SqlOrderRepository\n"
                    "repo = SqlOrderRepository()\n"
                ),
            }
        )
        self.assertNotIn(
            "composition.instantiation-outside", ids(report, "medium")
        )

    def test_adapter_of_one_family_instantiating_the_other_is_a_violation(self):
        report = audit_tree(
            {
                "src/adapters/driving/api.py": "class Api:\n    pass\n",
                "src/adapters/driven/sql_repo.py": (
                    "from src.adapters.driving.api import Api\n"
                    "class SqlRepo:\n"
                    "    def __init__(self):\n"
                    "        self.api = Api()\n"
                ),
            }
        )
        self.assertIn(
            (
                "composition.instantiation-outside",
                "src/adapters/driven/sql_repo.py",
                4,
            ),
            with_severity(report, "medium"),
        )

    def test_instantiation_in_comments_and_strings_is_ignored(self):
        report = audit_tree(
            {
                "src/adapters/driven/sql_repo.py": "class SqlRepo:\n    pass\n",
                "src/application/service.py": (
                    "# repo = SqlRepo()\n"
                    "note = \"repo = SqlRepo()\"\n"
                    "doc = '''\n"
                    "repo = SqlRepo()\n"
                    "'''\n"
                ),
            }
        )
        self.assertNotIn(
            "composition.instantiation-outside", ids(report, "medium")
        )

    def test_go_struct_literal_and_constructor_are_instantiation(self):
        report = audit_tree(
            {
                "internal/adapters/driven/sql.go": (
                    "package driven\n"
                    "type SQLOrders struct{}\n"
                    "func NewSQLOrders() SQLOrders { return SQLOrders{} }\n"
                ),
                "internal/domain/order.go": (
                    "package domain\n"
                    "func f() {\n"
                    "    _ = driven.SQLOrders{}\n"
                    "    _ = driven.NewSQLOrders()\n"
                    "}\n"
                ),
            }
        )
        instantiation = [
            finding
            for finding in report["findings"]
            if finding["id"] == "composition.instantiation-outside"
        ]
        self.assertEqual(
            [
                (finding["severity"], finding["file"], finding["line"])
                for finding in instantiation
            ],
            [
                ("medium", "internal/domain/order.go", 3),
                ("medium", "internal/domain/order.go", 4),
            ],
        )

    def test_application_class_is_a_composition_root(self):
        report = audit_tree(
            {
                "src/main/java/com/acme/Application.java": (
                    "package com.acme;\n"
                    "public class Application {\n"
                    "    Object repo = new JdbcOrders();\n"
                    "}\n"
                ),
                "src/main/java/com/acme/adapters/driven/JdbcOrders.java": (
                    "package com.acme.adapters.driven;\n"
                    "public class JdbcOrders {}\n"
                ),
            }
        )
        self.assertNotIn(
            "composition.instantiation-outside", ids(report, "medium")
        )

    def test_application_stem_is_a_composition_root_only_in_java(self):
        report = audit_tree(
            {
                "src/Application.java": "class Application {}\n",
                "src/application.ts": "export class Service {}\n",
                "src/application.go": "package main\n",
                "src/application.py": (
                    "from src.adapters.driven.sql_repo import SqlRepo\n"
                    "repo = SqlRepo()\n"
                ),
                "src/adapters/driven/sql_repo.py": "class SqlRepo:\n    pass\n",
            }
        )
        self.assertEqual(report["roles"]["src/Application.java"], "composition")
        self.assertNotEqual(report["roles"]["src/application.ts"], "composition")
        self.assertNotEqual(report["roles"]["src/application.go"], "composition")
        self.assertIn(
            (
                "composition.instantiation-outside",
                "src/application.py",
                2,
            ),
            with_severity(report, "medium"),
        )

    def test_instantiation_outside_composition_root(self):
        report = audit_tree(
            {
                "src/application/service.py": (
                    "from src.adapters.driven.sql_repo import SqlRepo\n"
                    "repo = SqlRepo()\n"
                ),
                "src/adapters/driven/sql_repo.py": "class SqlRepo:\n    pass\n",
                "src/main.py": (
                    "from src.adapters.driven.sql_repo import SqlRepo\n"
                    "repo = SqlRepo()\n"
                ),
            }
        )
        medium = [
            finding
            for finding in report["findings"]
            if finding["id"] == "composition.instantiation-outside"
        ]
        self.assertEqual(
            [(finding["severity"], finding["file"], finding["line"]) for finding in medium],
            [("medium", "src/application/service.py", 2)],
        )


class PortsTest(unittest.TestCase):
    def test_port_name_with_technology(self):
        report = audit_tree(
            {
                "src/ports/postgres_port.py": "class PostgresPort:\n    pass\n",
                "src/ports/orders.py": "class ForOrders:\n    pass\n",
            }
        )
        self.assertEqual(
            with_severity(report, "low"),
            [("port.technology-name", "src/ports/postgres_port.py", 1)],
        )

    def test_driven_port_without_in_memory_double(self):
        report = audit_tree(
            {
                "src/ports/order_repository.py": (
                    "from typing import Protocol\n"
                    "class OrderRepository(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
                "src/adapters/driven/sql_repo.py": (
                    "class SqlRepo:\n"
                    "    def save(self, order): ...\n"
                ),
            }
        )
        self.assertIn(
            ("tests.driven-port-without-double", "src/ports/order_repository.py", 2),
            with_severity(report, "medium"),
        )

    def test_driven_port_with_in_memory_double_is_quiet(self):
        report = audit_tree(
            {
                "src/ports/order_repository.py": (
                    "from typing import Protocol\n"
                    "class OrderRepository(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
                "src/adapters/driven/sql_repo.py": (
                    "class SqlRepo:\n"
                    "    def save(self, order): ...\n"
                ),
                "tests/test_orders.py": (
                    "class InMemoryOrderRepository:\n"
                    "    def save(self, order): ...\n"
                ),
            }
        )
        self.assertNotIn(
            "tests.driven-port-without-double",
            ids(report, "medium"),
        )

    def test_canonical_for_storing_orders_without_a_double(self):
        report = audit_tree(
            {
                "src/core/ports/for_storing_orders.py": (
                    "from typing import Protocol\n"
                    "class ForStoringOrders(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
            }
        )
        self.assertIn(
            (
                "tests.driven-port-without-double",
                "src/core/ports/for_storing_orders.py",
                2,
            ),
            with_severity(report, "medium"),
        )

    def test_framework_mock_is_not_an_in_memory_double(self):
        report = audit_tree(
            {
                "src/ports/order_repository.py": (
                    "from typing import Protocol\n"
                    "class OrderRepository(Protocol):\n"
                    "    def save(self, order): ...\n"
                ),
                "tests/test_orders.py": (
                    "from unittest.mock import Mock\n"
                    "from src.ports.order_repository import OrderRepository\n"
                    "repo = Mock(spec=OrderRepository)\n"
                ),
            }
        )
        self.assertIn(
            "tests.driven-port-without-double",
            ids(report, "medium"),
        )


class CoreTestsTest(unittest.TestCase):
    def test_core_without_isolated_tests(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/integration/test_api.py": "def test_api():\n    pass\n",
            }
        )
        self.assertIn(
            ("tests.core-without-tests", "", 0),
            with_severity(report, "medium"),
        )

    def test_core_name_in_a_comment_does_not_count_as_a_test(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/test_db.py": "# order\ndef test_db():\n    pass\n",
            }
        )
        self.assertIn(
            ("tests.core-without-tests", "", 0),
            with_severity(report, "medium"),
        )

    def test_infrastructure_test_that_mentions_the_core_does_not_count(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/test_db.py": (
                    "import psycopg2\n"
                    "class OrderTable:\n"
                    "    pass\n"
                ),
            }
        )
        self.assertIn(
            ("tests.core-without-tests", "", 0),
            with_severity(report, "medium"),
        )


class PythonDiscoveryTest(unittest.TestCase):
    def test_tests_folder_without_init_or_pytest_config(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/test_order.py": "def test_order():\n    pass\n",
            }
        )
        self.assertIn(
            ("tests.python-discovery", "tests", 0),
            with_severity(report, "low"),
        )

    def test_tests_init_file_is_quiet(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/__init__.py": "",
                "tests/test_order.py": "def test_order():\n    pass\n",
            }
        )
        self.assertNotIn("tests.python-discovery", ids(report, "low"))

    def test_pytest_config_is_quiet(self):
        report = audit_tree(
            {
                "src/domain/order.py": "class Order:\n    pass\n",
                "tests/test_order.py": "def test_order():\n    pass\n",
                "pyproject.toml": "[tool.pytest.ini_options]\n",
            }
        )
        self.assertNotIn("tests.python-discovery", ids(report, "low"))


class ConfigurationTest(unittest.TestCase):
    def test_explicit_config_wins_over_inference(self):
        report = audit_tree(
            {
                "weird/order.py": (
                    "from lib.repo import Repo\n"
                    "class Order:\n"
                    "    pass\n"
                ),
                "lib/repo.py": "class Repo:\n    pass\n",
            },
            config={
                "core": ["weird"],
                "ports": [],
                "driving_adapters": ["lib"],
                "driven_adapters": [],
                "composition_root": [],
                "forbidden_in_core": [],
            },
        )
        self.assertEqual(report["config"], "explicit")
        self.assertEqual(
            with_severity(report, "high"),
            [("core.imports-adapter", "weird/order.py", 1)],
        )

    def test_structure_not_detectable(self):
        report = audit_tree({"README.md": "# nothing\n"})
        self.assertEqual(report["config"], "inferred")
        self.assertEqual(ids(report, "info"), ["structure.not-detected"])

    def test_config_extends_forbidden_libraries(self):
        report = audit_tree(
            {
                "src/domain/order.py": (
                    "import acme_io\n"
                    "class Order:\n"
                    "    pass\n"
                ),
            },
            config={
                "core": ["src/domain"],
                "ports": [],
                "driving_adapters": [],
                "driven_adapters": [],
                "composition_root": [],
                "forbidden_in_core": ["acme_io"],
            },
        )
        self.assertEqual(
            with_severity(report, "high"),
            [("core.forbidden-library", "src/domain/order.py", 1)],
        )


class IgnoredDirectoriesTest(unittest.TestCase):
    def test_node_modules_is_not_audited(self):
        report = audit_tree(
            {
                "node_modules/pkg/index.js": (
                    "import express from 'express';\n"
                ),
                "src/domain/order.py": "class Order:\n    pass\n",
            }
        )
        self.assertEqual(
            [path for path in report["roles"] if path.startswith("node_modules/")],
            [],
        )


class CliTest(unittest.TestCase):
    def test_missing_path_exits_with_2(self):
        process = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "audit.py"),
                "--path",
                "/path/that/does/not/exist",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 2)


if __name__ == "__main__":
    unittest.main()
