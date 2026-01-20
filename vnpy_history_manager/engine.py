"""
历史数据管理器引擎
"""

from vnpy.trader.engine import BaseEngine, MainEngine, EventEngine
from vnpy.trader.history_manager import HistoryManager


class HistoryManagerEngine(BaseEngine):
    """历史数据管理器引擎"""
    
    def __init__(self, main_engine: MainEngine, event_engine: EventEngine):
        """初始化"""
        super().__init__(main_engine, event_engine, "HistoryManager")
        
        # 创建历史数据管理器
        self.history_manager = HistoryManager(main_engine)
        
    def get_manager(self) -> HistoryManager:
        """获取历史数据管理器"""
        return self.history_manager
