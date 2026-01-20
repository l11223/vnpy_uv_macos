import numpy as np
from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)
from vnpy.trader.constant import Interval


class TurtleStrategy(CtaTemplate):
    """
    海龟交易法则简化版 (System 1)
    核心逻辑：唐奇安通道突破
    """
    author = "User"

    # ---------------------------------------------------------------------------------------
    # 参数定义
    # ---------------------------------------------------------------------------------------
    entry_window = 20   # 入场周期 (海龟默认为20)
    exit_window = 10    # 出场周期 (海龟默认为10)
    fixed_size = 1      # 下单手数

    # ---------------------------------------------------------------------------------------
    # 变量定义
    # ---------------------------------------------------------------------------------------
    entry_up = 0.0      # 入场上轨 (过去20根K线最高价)
    entry_down = 0.0    # 入场下轨 (过去20根K线最低价)
    exit_up = 0.0       # 出场上轨 (过去10根K线最高价)
    exit_down = 0.0     # 出场下轨 (过去10根K线最低价)

    parameters = ["entry_window", "exit_window", "fixed_size"]
    variables = ["entry_up", "entry_down", "exit_up", "exit_down"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        self.write_log("海龟策略初始化")
        self.load_bar(20) # 至少加载入场周期所需的数据

    def on_start(self):
        self.write_log("海龟策略启动")

    def on_stop(self):
        self.write_log("海龟策略停止")

    def on_tick(self, tick: TickData):
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # -----------------------------------------------------------------------------------
        # 1. 计算唐奇安通道
        # 注意：为了避免"未来函数"，我们应该计算【不包含当前K线】的过去N根K线的极值
        # am.high 是一个 numpy 数组，[:-1] 表示切片去掉最后一个（也就是当前的）数据
        # -----------------------------------------------------------------------------------
        
        # 计算入场轨道 (基于20周期)
        # 获取过去20根K线（不含当前）的最高/最低
        entry_up = np.max(am.high[-self.entry_window-1:-1])
        entry_down = np.min(am.low[-self.entry_window-1:-1])
        
        # 计算出场轨道 (基于10周期)
        exit_up = np.max(am.high[-self.exit_window-1:-1])
        exit_down = np.min(am.low[-self.exit_window-1:-1])

        # 更新变量到界面
        self.entry_up = entry_up
        self.entry_down = entry_down
        self.exit_up = exit_up
        self.exit_down = exit_down

        # -----------------------------------------------------------------------------------
        # 2. 交易逻辑
        # -----------------------------------------------------------------------------------
        
        # 获取当前价格
        price = bar.close_price
        
        # 如果空仓
        if self.pos == 0:
            # 突破上轨 -> 买开
            if price > entry_up:
                self.buy(price + 5, self.fixed_size) # 挂高价保证成交
                
            # 跌破下轨 -> 卖开
            elif price < entry_down:
                self.short(price - 5, self.fixed_size)

        # 如果持有多单
        elif self.pos > 0:
            # 跌破短期下轨 -> 平仓止损/止盈
            if price < exit_down:
                self.sell(price - 5, abs(self.pos))

        # 如果持有空单
        elif self.pos < 0:
            # 突破短期上轨 -> 平仓止损/止盈
            if price > exit_up:
                self.cover(price + 5, abs(self.pos))

    def on_order(self, order: OrderData):
        pass

    def on_trade(self, trade: TradeData):
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        pass
