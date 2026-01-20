from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.constant import Interval
from vnpy.trader.object import HistoryRequest
from mootdx.reader import Reader
from .tdx_datafeed import TdxDatafeed

class TdxEngine(BaseEngine):
    """
    Mootdx 数据服务引擎
    """

    def __init__(self, main_engine: MainEngine, event_engine):
        """构造函数"""
        super().__init__(main_engine, event_engine, "mootdx")
        self.datafeed = TdxDatafeed()

    def query_history(self, req: HistoryRequest):
        """查询历史数据"""
        return self.datafeed.get_bars(
            req.symbol,
            req.exchange,
            req.interval,
            req.start,
            req.end,
        )