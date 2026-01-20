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


class MyStrategy(CtaTemplate):
    """
    用户自定义策略模板
    """
    author = "User"

    # 定义参数（可以在界面或配置中修改）
    fast_window = 10
    slow_window = 20
    fixed_size = 1

    # 定义运行时变量（界面显示用）
    fast_ma0 = 0.0
    slow_ma0 = 0.0

    parameters = ["fast_window", "slow_window", "fixed_size"]
    variables = ["fast_ma0", "slow_ma0"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """策略初始化"""
        self.write_log("策略初始化")
        # 加载10天历史数据用于初始化
        self.load_bar(10)

    def on_start(self):
        """策略启动"""
        self.write_log("策略启动")

    def on_stop(self):
        """策略停止"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """Tick数据更新"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """K线数据更新"""
        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 计算技术指标
        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]

        # 判断交易信号
        cross_over = fast_ma[-1] > slow_ma[-1] and fast_ma[-2] <= slow_ma[-2]
        cross_below = fast_ma[-1] < slow_ma[-1] and fast_ma[-2] >= slow_ma[-2]

        # 执行交易
        if cross_over:
            if self.pos == 0:
                self.buy(bar.close_price + 5, self.fixed_size)
            elif self.pos < 0:
                self.cover(bar.close_price + 5, self.fixed_size)
                self.buy(bar.close_price + 5, self.fixed_size)

        elif cross_below:
            if self.pos == 0:
                self.short(bar.close_price - 5, self.fixed_size)
            elif self.pos > 0:
                self.sell(bar.close_price - 5, self.fixed_size)
                self.short(bar.close_price - 5, self.fixed_size)

    def on_order(self, order: OrderData):
        """订单状态更新"""
        pass

    def on_trade(self, trade: TradeData):
        """成交信息更新"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """停止单更新"""
        pass
