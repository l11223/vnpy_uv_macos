"""
历史数据管理器 App 定义
"""

from pathlib import Path
from vnpy.trader.app import BaseApp
from vnpy.trader.engine import BaseEngine

from .engine import HistoryManagerEngine


class HistoryManagerApp(BaseApp):
    """历史数据管理器"""
    
    app_name: str = "HistoryManager"
    app_module: str = "vnpy_history_manager"
    app_path: Path = Path(__file__).parent
    display_name: str = "历史数据管理"
    engine_class: type[BaseEngine] = HistoryManagerEngine
    widget_name: str = "HistoryManagerWidget"
    icon_name: str = "database.ico"
