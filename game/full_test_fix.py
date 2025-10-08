"""Adaptive full-flow test harness with gate-controlled phases."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from full_flow_logger import FullFlowTestLogger

# Ensure project root on path when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_PARENT = PROJECT_ROOT.parent
if str(PROJECT_PARENT) not in sys.path:
    sys.path.insert(0, str(PROJECT_PARENT))

from game.core.models.config import GameConfig
from game.core.models.data_models import Task
from game.naga_game_system import NagaGameSystem


@dataclass
class PhaseResult:
    name: str
    data: Dict[str, Any]


async def run_full_flow_test(
    user_question: str,
    max_phases: Optional[int] = None,
    expected_agent_count: Optional[tuple[int, int]] = None,
) -> Dict[str, Any]:
    """Run the full flow with an optional phase-count limit."""

    logger = FullFlowTestLogger("动态全流程测试")
    logger.log_step("测试开始", {"question": user_question, "max_phases": max_phases})
    logger.test_data["user_question"] = user_question

    if max_phases is not None and max_phases <= 0:
        max_phases = None

    try:
        phases: List[PhaseResult] = []

        # Phase 1: system init & config
        config = await _phase_setup(logger)
        phases.append(config)
        if max_phases is not None and len(phases) >= max_phases:
            return _finalize(logger, phases, success=True, reason="phase_limit")

        # Phase 2: task bootstrapping (no domain inference)
        task_phase = await _phase_prepare_task(logger, user_question)
        task: Task = task_phase.data["task"]
        phases.append(task_phase)
        if max_phases is not None and len(phases) >= max_phases:
            return _finalize(logger, phases, success=True, reason="phase_limit")

        # Phase 3: agent generation
        agents_phase = await _phase_generate_agents(logger, task, expected_agent_count)
        agents = agents_phase.data["agents"]
        phases.append(agents_phase)
        if max_phases is not None and len(phases) >= max_phases:
            return _finalize(logger, phases, success=True, reason="phase_limit")

        # Phase 4: interaction graph
        graph_phase = await _phase_build_graph(logger, task, agents)
        interaction_graph = graph_phase.data["interaction_graph"]
        phases.append(graph_phase)
        if max_phases is not None and len(phases) >= max_phases:
            return _finalize(logger, phases, success=True, reason="phase_limit")

        # Phase 5: user request processing
        response_phase = await _phase_process_request(logger, task, interaction_graph, user_question)
        response = response_phase.data["response"]
        phases.append(response_phase)
        if max_phases is not None and len(phases) >= max_phases:
            return _finalize(
                logger,
                phases,
                success=True,
                reason="phase_limit",
                extra={"result": response.content},
            )

        # Phase 6: self game session
        game_phase = await _phase_self_game(logger, task, agents)
        session = game_phase.data["session"]
        phases.append(game_phase)

        final_result = session.final_result.actor_output.content if (session.final_result and session.final_result.actor_output) else response.content
        return _finalize(
            logger,
            phases,
            success=True,
            extra={
                "result": final_result,
                "agents_generated": len(agents),
            },
        )

    except Exception as exc:  # pragma: no cover - placeholder for runtime errors
        logger.log_error(exc, "full_flow")
        return _finalize(logger, phases, success=False, extra={"error": str(exc)})


async def _phase_setup(logger: FullFlowTestLogger) -> PhaseResult:
    logger.log_step("系统初始化")
    config_path = PROJECT_PARENT / "config.json"
    config_data: Dict[str, Any]
    if config_path.exists():
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        logger.log_step("配置加载成功", {"has_config": True})
    else:
        config_data = {}
        logger.log_step("使用默认配置")

    game_config = GameConfig()
    naga_system = NagaGameSystem(game_config)
    logger.log_step("NagaGameSystem创建成功")
    logger.test_data["config"] = {"loaded": bool(config_data)}
    logger._game_config = game_config  # type: ignore[attr-defined]
    logger._naga_system = naga_system  # type: ignore[attr-defined]
    return PhaseResult(
        name="setup",
        data={"config": config_data, "game_config": game_config, "naga_system": naga_system},
    )


async def _phase_prepare_task(
    logger: FullFlowTestLogger,
    user_question: str,
) -> PhaseResult:
    logger.log_step("创建任务对象")
    task = Task(
        task_id=f"test_{int(time.time())}",
        description=user_question,
        domain="",
        requirements=[user_question],
        constraints=[],
    )
    logger.test_data["task"] = {"task_id": task.task_id, "description": task.description}
    return PhaseResult("task", {"task": task})


async def _phase_generate_agents(
    logger: FullFlowTestLogger,
    task: Task,
    expected_agent_count: Optional[tuple[int, int]],
) -> PhaseResult:
    naga_system = _require_system(logger)
    logger.log_step("开始生成智能体团队")
    agents = await naga_system.generate_agents_only(task, expected_agent_count)

    if not agents:
        raise RuntimeError("未生成任何智能体")

    agent_summaries = []
    for agent in agents:
        summary = {
            "name": agent.name,
            "role": agent.role,
            "is_requester": agent.is_requester,
        }
        agent_summaries.append(summary)
        logger.log_node_output(agent.name, "需求方" if agent.is_requester else "执行者", agent.role)

    logger.test_data["generated_agents"] = agent_summaries
    return PhaseResult("agents", {"agents": agents})


async def _phase_build_graph(
    logger: FullFlowTestLogger,
    task: Task,
    agents: List[Any],
) -> PhaseResult:
    naga_system = _require_system(logger)
    logger.log_step("构建交互图")
    interaction_graph = await naga_system._execute_interaction_graph_phase(agents, task)
    logger.test_data["interaction_graph"] = {
        "agent_count": len(interaction_graph.agents),
        "connections": sum(len(agent.connection_permissions) for agent in interaction_graph.agents),
    }
    return PhaseResult("graph", {"interaction_graph": interaction_graph})


async def _phase_process_request(
    logger: FullFlowTestLogger,
    task: Task,
    interaction_graph: Any,
    user_question: str,
) -> PhaseResult:
    naga_system = _require_system(logger)
    logger.log_step("执行用户问题处理流程")
    response = await naga_system.user_interaction_handler.process_user_request(
        user_question,
        interaction_graph,
        user_id="test_user",
    )
    logger.log_node_output("系统", "响应", response.content)
    logger.test_data["final_result"] = response.content
    return PhaseResult("response", {"response": response})


async def _phase_self_game(
    logger: FullFlowTestLogger,
    task: Task,
    agents: List[Any],
) -> PhaseResult:
    naga_system = _require_system(logger)
    logger.log_step("启动自博弈引擎")
    session = await naga_system.game_engine.start_game_session(task, agents, context=None)

    logger.test_data["game_rounds"] = _summarize_rounds(session.rounds)
    if session.final_result and session.final_result.actor_output:
        logger.test_data["final_result"] = session.final_result.actor_output.content
    return PhaseResult("self_game", {"session": session})


def _require_system(logger: FullFlowTestLogger) -> NagaGameSystem:
    system = getattr(logger, "_naga_system", None)
    if system is None:
        raise RuntimeError("System not initialised; setup phase must run first")
    return system


def _summarize_rounds(rounds: List[Any]) -> List[Dict[str, Any]]:
    summary = []
    for rnd in rounds or []:
        summary.append(
            {
                "round": rnd.round_number,
                "phase": rnd.phase,
                "decision": rnd.decision,
            }
        )
    return summary


def _finalize(
    logger: FullFlowTestLogger,
    phases: List[PhaseResult],
    success: bool,
    reason: str = "completed",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    logger.test_data["phases"] = [phase.name for phase in phases]
    logger.test_data["termination_reason"] = reason
    logger.finalize_test(success)

    result: Dict[str, Any] = {
        "success": success,
        "log_file": str(logger.log_file),
        "report_file": str(logger.report_file),
        "phases": [phase.name for phase in phases],
        "termination_reason": reason,
    }

    agent_phase = next((phase for phase in phases if phase.name == "agents"), None)
    if agent_phase:
        result["agents_generated"] = len(agent_phase.data.get("agents", []))

    if extra:
        result.update(extra)
    return result


async def main() -> None:
    print("🎮 NagaAgent Game 测试")
    print("=" * 60)

    question = input("请输入测试问题: ").strip()
    if not question:
        question = "我想创建一个帮助学生学习编程的智能平台"

    phase_limit_input = input("可选：输入要执行的阶段数量 (1-6) 以提前结束: ").strip()
    if phase_limit_input.isdigit():
        max_phase_value = int(phase_limit_input)
        max_phases = max_phase_value if max_phase_value > 0 else None
    else:
        max_phases = None
    result = await run_full_flow_test(question, max_phases=max_phases)

    print("\n结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
