#!/usr/bin/env python3
"""Role generation integration smoke test.

Exercises the agent generation pipeline and verifies prompt export artifacts.
"""

import asyncio
import sys
import unittest
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from game.core.models.config import GameConfig
from game.core.models.data_models import Task
from game.core.interaction_graph.role_generator import RoleGenerator


class RoleGenerationSmokeTest(unittest.TestCase):
    def setUp(self):
        self.config = GameConfig()
        self.role_generator = RoleGenerator(self.config)
        self.task = Task(
            task_id="test_role_generation",
            description="为一款健康饮食应用设计功能模块",
            domain="产品设计",
            requirements=[
                "提供个性化饮食建议",
                "支持进度追踪"
            ],
            constraints=[
                "两周内交付",
                "移动端优先"
            ],
            max_iterations=3
        )

    def tearDown(self):
        export_path = self.role_generator.last_prompt_export_path
        if export_path and export_path.exists():
            try:
                export_path.unlink()
            except OSError:
                pass

    def test_role_generation_and_prompt_export(self):
        agents = asyncio.run(self.role_generator.generate_agents(self.task, (3, 4)))

        # system should include requester + generated roles
        self.assertGreaterEqual(len(agents), 4)

        export_path = self.role_generator.last_prompt_export_path
        self.assertIsNotNone(export_path, "prompt export path should be set")
        self.assertTrue(export_path.exists(), "exported prompt file should exist")

        with zipfile.ZipFile(export_path) as zf:
            sheet_xml = zf.read("xl/worksheets/sheet1.xml")

        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        root = ET.fromstring(sheet_xml)
        sheet_data = root.find(f"{ns}sheetData")
        rows = list(sheet_data.findall(f"{ns}row"))

        headers = []
        for cell in rows[0].findall(f"{ns}c"):
            text_elem = cell.find(f"{ns}is/{ns}t")
            headers.append(text_elem.text if text_elem is not None else "")
        expected_headers = [
            "timestamp",
            "task_id",
            "task_domain",
            "task_description",
            "role_name",
            "role_type",
            "priority_level",
            "connections",
            "responsibilities",
            "skills",
            "system_prompt"
        ]
        self.assertEqual(headers, expected_headers)

        data_rows = rows[1:]
        self.assertGreaterEqual(len(data_rows), 3, "should log prompts for generated roles")
        for row in data_rows:
            cells = row.findall(f"{ns}c")
            values = []
            for cell in cells:
                text_elem = cell.find(f"{ns}is/{ns}t")
                values.append(text_elem.text if text_elem is not None else "")
            role_name = values[4]
            system_prompt = values[10]
            self.assertTrue(role_name, "role name should be populated")
            self.assertTrue(system_prompt and len(system_prompt) > 20, "system prompt should contain content")


if __name__ == "__main__":
    unittest.main()
