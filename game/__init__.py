"""NagaAgent Game - 多智能体博弈系统"""

from importlib import import_module

from .core.models.data_models import (
    Agent,
    InteractionGraph, 
    GameResult,
    HiddenState,
    TextBlock,
    NoveltyScore,
    GeneratedRole,
    RoleGenerationRequest,
    PromptTemplate,
    ThinkingVector
)

from .core.interaction_graph.role_generator import RoleGenerator
from .core.interaction_graph.signal_router import SignalRouter
from .core.interaction_graph.dynamic_dispatcher import DynamicDispatcher
from .core.interaction_graph.distributor import Distributor
from .core.interaction_graph.prompt_generator import PromptGenerator

from .naga_game_system import NagaGameSystem

__version__ = "1.0.0"
__author__ = "NagaAgent Team"

_LAZY_IMPORTS = {
    'GameActor': 'game.core.self_game.actor:GameActor',
    'GameCriticizer': 'game.core.self_game.criticizer:GameCriticizer',
    'PhilossChecker': 'game.core.self_game.checker.philoss_checker:PhilossChecker',
    'GameEngine': 'game.core.self_game.game_engine:GameEngine',
}

__all__ = [
    'Agent',
    'InteractionGraph', 
    'GameResult',
    'HiddenState',
    'TextBlock',
    'NoveltyScore',
    'GeneratedRole',
    'RoleGenerationRequest', 
    'PromptTemplate',
    'ThinkingVector',
    'RoleGenerator',
    'SignalRouter', 
    'DynamicDispatcher',
    'Distributor',
    'PromptGenerator',
    'GameActor',
    'GameCriticizer',
    'PhilossChecker',
    'GameEngine',
    'NagaGameSystem',
]


def __getattr__(name):
    if name in _LAZY_IMPORTS:
        module_path, attr = _LAZY_IMPORTS[name].split(":")
        module = import_module(module_path)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'game' has no attribute '{name}'")
