"""Minimal logging helper used by the full flow tests."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class FullFlowTestLogger:
    """Small helper for capturing logs and a markdown summary of a test run."""

    def __init__(self, test_name: str, log_root: Optional[Path] = None, logger: Optional[logging.Logger] = None) -> None:
        self.test_name = test_name
        self.start_time = datetime.now()
        self.log_dir = log_root or Path("logs/full_flow_test")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"test_{timestamp}.log"
        self.report_file = self.log_dir / f"result_{timestamp}.md"

        self.logger = logger or logging.getLogger(f"full_flow.{timestamp}")
        if logger is None:
            self._configure_logger()

        self.test_data = self._initial_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def log_step(self, step: str, data: Any = None) -> None:
        self.logger.info("Step: %s", step)
        if data is not None:
            self.logger.debug("data=%s", json.dumps(data, ensure_ascii=False, indent=2))

    def log_node_output(self, node_name: str, node_type: str, output: str) -> None:
        self.logger.info("Node[%s/%s]: %s", node_type, node_name, output)

    def log_error(self, error: Exception, context: str = "") -> None:
        label = f" ({context})" if context else ""
        self.logger.error("Error%s: %s", label, error, exc_info=True)
        self.test_data["errors"].append(
            {
                "context": context or "general",
                "error": str(error),
                "timestamp": datetime.now().isoformat(),
            }
        )

    def finalize_test(self, success: bool) -> None:
        end_time = datetime.now()
        self.test_data["end_time"] = end_time.isoformat()
        self.test_data["execution_time"] = (end_time - self.start_time).total_seconds()
        self.test_data["success"] = success

        self._write_report()
        outcome = "成功" if success else "失败"
        duration = self.test_data.get("execution_time") or 0.0
        self.logger.info("Test finished: %s (%.2f 秒)", outcome, duration)
        self.logger.info("Report written to %s", self.report_file)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _configure_logger(self) -> None:
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        self.logger.propagate = False

    def _initial_state(self) -> Dict[str, Any]:
        return {
            "test_name": self.test_name,
            "start_time": self.start_time.isoformat(),
            "end_time": None,
            "user_question": None,
            "inferred_domain": None,
            "generated_agents": [],
            "interaction_graph": None,
            "game_rounds": [],
            "final_result": None,
            "execution_time": None,
            "success": False,
            "errors": [],
            "pareto_front": [],
            "prompt_export_file": None,
        }

    def _write_report(self) -> None:
        self.report_file.write_text(self._build_report(), encoding="utf-8")

    def _build_report(self) -> str:
        data = self.test_data
        end_time = data.get("end_time") or "N/A"
        exec_time = data.get("execution_time") or 0.0
        result_label = "✅ 成功" if data.get("success") else "❌ 失败"

        lines = [
            "# NagaAgent Game 全流程测试报告",
            "",
            "## 测试概要",
            f"- **测试名称**: {data['test_name']}",
            f"- **开始时间**: {data['start_time']}",
            f"- **结束时间**: {end_time}",
            f"- **执行时间**: {exec_time:.2f}秒",
            f"- **测试结果**: {result_label}",
        ]

        if data.get("user_question"):
            lines.extend([
                "",
                "## 用户输入",
                data["user_question"],
            ])

        if data.get("inferred_domain"):
            lines.extend([
                "",
                "## 领域推断",
                f"- **结果**: {data['inferred_domain']}",
            ])

        agents = data.get("generated_agents") or []
        if agents:
            lines.extend(["", "## 智能体概览"])
            for agent in agents:
                name = agent.get("name") or "Unknown"
                role = agent.get("role") or "N/A"
                marker = "需求方" if agent.get("is_requester") else "执行者"
                lines.append(f"- {name} ({marker}, 角色: {role})")

        if data.get("interaction_graph"):
            graph = data["interaction_graph"]
            lines.extend(
                [
                    "",
                    "## 交互图摘要",
                    f"- **智能体数量**: {graph.get('agent_count', 'N/A')}",
                    f"- **连接数量**: {graph.get('connections', 'N/A')}",
                ]
            )

        rounds = data.get("game_rounds") or []
        if rounds:
            lines.extend([
                "",
                "## 博弈统计",
                f"- **轮次数量**: {len(rounds)}",
            ])

        if data.get("pareto_front"):
            lines.extend([
                "",
                "## 帕累托前沿",
                f"- **方案数量**: {len(data['pareto_front'])}",
            ])

        if data.get("prompt_export_file"):
            lines.extend([
                "",
                "## 提示词导出",
                f"- **文件**: {data['prompt_export_file']}",
            ])

        if data.get("final_result"):
            lines.extend([
                "",
                "## 最终结果",
                data["final_result"],
            ])

        errors = data.get("errors") or []
        lines.extend(["", "## 错误信息"])
        if errors:
            for err in errors:
                lines.append(f"- **{err['context']}**: {err['error']}")
        else:
            lines.append("无")

        lines.extend([
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
        ])

        return "\n".join(lines)
