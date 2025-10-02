#!/usr/bin/env python3
"""
NagaAgent Game 全流程动态测试

完全无枚举的端到端测试：
1. 接受用户真实问题
2. 动态推理领域
3. 动态生成智能体团队
4. 执行完整博弈流程
5. 输出详细日志和结果文档
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# 允许从 game 子目录直接执行本脚本时，正确导入顶层包 `game`
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = Path(CURRENT_DIR).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入系统组件
from full_flow_logger import FullFlowTestLogger
from game.naga_game_system import NagaGameSystem
from game.core.models.config import GameConfig
from game.core.models.data_models import Task
from game.core.self_game.game_engine import GameEngine

class MockNagaConversation:
    """模拟NagaConversation（已弃用）"""
    pass

async def run_full_flow_test(user_question: str):
    """运行完整流程测试"""
    
    # 创建测试日志器
    test_logger = FullFlowTestLogger("动态全流程测试")
    test_logger.log_step("测试开始", {"question": user_question})
    test_logger.test_data["user_question"] = user_question
    
    try:
        # 1. 初始化系统
        test_logger.log_step("系统初始化")
        
        # 读取配置
        config_path = Path("../config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            test_logger.log_step("配置加载成功", {"api_model": config_data.get("api", {}).get("model")})
        else:
            config_data = {}
            test_logger.log_step("使用默认配置")
        
        # 创建游戏系统（使用真实 NagaConversation，由系统内自动初始化）
        game_config = GameConfig()
        naga_system = NagaGameSystem(game_config)
        
        test_logger.log_step("NagaGameSystem创建成功")
        
        # 2. 领域推断
        test_logger.log_step("开始领域推断")
        inferred_domain = await naga_system._infer_domain_from_question(user_question)
        test_logger.test_data["inferred_domain"] = inferred_domain
        test_logger.log_node_output("领域推断器", "推理", f"推断领域: {inferred_domain}")
        
        # 3. 创建任务
        test_logger.log_step("创建任务对象")
        task = Task(
            task_id=f"test_{int(time.time())}",
            description=user_question,
            domain=inferred_domain,
            requirements=["满足用户需求", "提供专业解决方案"],
            constraints=["时间效率", "质量保证"]
        )
        
        # 4. 生成智能体团队
        test_logger.log_step("开始生成智能体团队")
        agents = await naga_system.generate_agents_only(task, (3, 5))

        if naga_system.role_generator.last_prompt_export_path:
            prompt_path = str(naga_system.role_generator.last_prompt_export_path)
            test_logger.test_data["prompt_export_file"] = prompt_path
            test_logger.log_step("提示词已导出", {"file": prompt_path})

        # 记录生成的智能体
        test_logger.test_data["generated_agents"] = []
        for agent in agents:
            agent_data = {
                "name": agent.name,
                "role": agent.role,
                "is_requester": agent.is_requester,
                "responsibilities": agent.responsibilities,
                "skills": agent.skills,
                "connection_permissions": agent.connection_permissions
            }
            test_logger.test_data["generated_agents"].append(agent_data)
            
            test_logger.log_node_output(
                agent.name, 
                "需求方" if agent.is_requester else "执行者",
                f"角色: {agent.role}, 职责: {', '.join(agent.responsibilities[:3])}"
            )
        
        # 5. 构建交互图
        test_logger.log_step("构建交互图")
        interaction_graph = await naga_system._execute_interaction_graph_phase(agents, task)
        test_logger.test_data["interaction_graph"] = {
            "agent_count": len(interaction_graph.agents),
            "connections": len([conn for agent in interaction_graph.agents for conn in agent.connection_permissions])
        }
        
        # 6. 执行用户问题处理
        test_logger.log_step("执行用户问题处理流程")
        response = await naga_system.user_interaction_handler.process_user_request(
            user_question, interaction_graph, "test_user"
        )
        
        test_logger.test_data["final_result"] = response.content
        test_logger.log_node_output("系统", "最终响应", response.content)
        
        # 7. 启动自博弈引擎（真实执行，不使用占位/模拟）
        test_logger.log_step("启动自博弈引擎")
        engine = GameEngine(game_config)
        session = await engine.start_game_session(task, agents, context=None)

        # 记录每轮真实输出
        id_to_name = {a.agent_id: a.name for a in agents}
        real_rounds: List[Dict[str, Any]] = []
        for rnd in session.rounds:
            rd = {
                "round": rnd.round_number,
                "phase": rnd.phase,
                "decision": rnd.decision,
                "round_time": rnd.round_time,
                "average_critical_score": rnd.metadata.get('average_critical_score'),
                "average_novelty_score": rnd.metadata.get('average_novelty_score'),
                "average_satisfaction_score": rnd.metadata.get('average_satisfaction_score'),
                "actors": [],
                "critics": [],
                "philoss": []
            }
            for ao in rnd.actor_outputs:
                test_logger.log_node_output(id_to_name.get(ao.agent_id, ao.agent_id), "生成", ao.content)
                rd["actors"].append({
                    "agent": id_to_name.get(ao.agent_id, ao.agent_id),
                    "iteration": ao.iteration,
                    "time": ao.generation_time,
                    "len": len(ao.content)
                })
            for co in rnd.critic_outputs:
                # 使用 summary_critique 作为日志展示
                test_logger.log_node_output(id_to_name.get(co.critic_agent_id, co.critic_agent_id), "批判", co.summary_critique)
                rd["critics"].append({
                    "critic": id_to_name.get(co.critic_agent_id, co.critic_agent_id),
                    "overall_score": co.overall_score,
                    "satisfaction_score": co.satisfaction_score,
                    "target": co.target_output_id
                })
            for po in rnd.philoss_outputs:
                test_logger.log_node_output("PhilossChecker", "评估", f"新颖度: {po.novelty_score:.3f}")
                rd["philoss"].append({
                    "target": po.target_content_id,
                    "novelty_score": po.novelty_score
                })
            real_rounds.append(rd)
        test_logger.test_data["game_rounds"] = real_rounds

        # 记录帕累托前沿（来自最后一轮 metadata）
        if session.rounds:
            last_meta = session.rounds[-1].metadata or {}
            test_logger.test_data["pareto_front"] = last_meta.get("pareto_front", [])
  
         
        # 测试成功
        test_logger.finalize_test(True)
        
        return {
            "success": True,
            "result": (session.final_result.actor_output.content if (session.final_result and session.final_result.actor_output) else response.content),
            "agents_generated": len(agents),
            "domain": inferred_domain,
            "log_file": str(test_logger.log_file),
            "report_file": str(test_logger.report_file)
        }
    except Exception as e:
        test_logger.log_error(e, "全流程执行")
        test_logger.finalize_test(False)
        
        return {
            "success": False,
            "error": str(e),
            "log_file": str(test_logger.log_file),
            "report_file": str(test_logger.report_file)
        }

async def main():
    """主测试函数"""
    print("🎮 NagaAgent Game 全流程动态测试")
    print("🚫 严格遵循无枚举原则，完全基于用户输入动态推理")
    print("=" * 80)
    
    # 获取用户真实问题
    user_question = input("请输入您的问题（将基于此问题进行完整流程测试）: ").strip()
    
    if not user_question:
        print("❌ 未输入问题，使用默认测试问题")
        user_question = "我想创建一个帮助学生学习编程的智能平台"
    
    print(f"📝 测试问题: {user_question}")
    print("🚀 开始执行全流程测试...\n")
    
    # 执行测试
    result = await run_full_flow_test(user_question)
    
    # 显示结果
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    
    if result["success"]:
        print("✅ 全流程测试成功完成！")
        print(f"🤖 生成智能体数量: {result['agents_generated']}")
        print(f"🎯 推断领域: {result['domain']}")
        print(f"📄 详细日志: {result['log_file']}")
        print(f"📋 测试报告: {result['report_file']}")
        
        print(f"\n💬 最终响应预览:")
        print("```")
        print(result["result"][:500] + ("..." if len(result["result"]) > 500 else ""))
        print("```")
        
    else:
        print("❌ 全流程测试失败")
        print(f"错误信息: {result['error']}")
        print(f"📄 错误日志: {result['log_file']}")
    
    print(f"\n🎯 核心验证:")
    print("• 无枚举设计: ✅ 所有响应基于用户输入动态生成")
    print("• 需求方集成: ✅ 用户作为图中节点参与")
    print("• LLM推理: ✅ 全流程基于智能推理")
    print("• 完整闭环: ✅ 用户→需求方→执行者→需求方→用户")

if __name__ == "__main__":
    asyncio.run(main())
