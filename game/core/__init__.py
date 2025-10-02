"""NagaAgent Game 核心包，采用惰性加载以避免重型依赖启动成本。"""

from importlib import import_module
from types import ModuleType
from typing import Any

_LAZY_MODULES = {
    'models': 'game.core.models',
    'interaction_graph': 'game.core.interaction_graph',
    'self_game': 'game.core.self_game',
}

_LAZY_ATTRS = {
    'GameActor': 'game.core.self_game.actor:GameActor',
    'GameCriticizer': 'game.core.self_game.criticizer:GameCriticizer',
    'PhilossChecker': 'game.core.self_game.checker.philoss_checker:PhilossChecker',
    'GameEngine': 'game.core.self_game.game_engine:GameEngine',
}

__all__ = list(_LAZY_MODULES.keys()) + list(_LAZY_ATTRS.keys())


def __getattr__(name: str) -> Any:
    if name in _LAZY_MODULES:
        module = import_module(_LAZY_MODULES[name])
        if not isinstance(module, ModuleType):  # pragma: no cover
            raise AttributeError(name)
        globals()[name] = module
        return module
    if name in _LAZY_ATTRS:
        module_path, attr = _LAZY_ATTRS[name].split(':')
        module = import_module(module_path)
        value = getattr(module, attr)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'game.core' has no attribute '{name}'")
