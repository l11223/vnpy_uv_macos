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
    author = "xcy"

    # -------------------------------------------------------------
    # 1. 定义参数 (Parameters)
    # 这些变量可以在策略界面手动修改，或者在回测时进行参数优化
    # --------------------------------------------------------------
    fast_window = 10    # 快速均线周期
    slow_window = 20    # 慢速均线周期
    rsi_window = 14     # RSI周期
    fixed_size = 1      # 每次下单手数

    # ---------------------------------------------------------------------------------------
    # 2. 定义变量 (Variables)
    # 这些变量用于在界面上实时显示策略的状态，只读，会自动更新到UI
    # ---------------------------------------------------------------------------------------
    fast_ma0 = 0.0      # 当前K线的快线值
    slow_ma0 = 0.0      # 当前K线的慢线值
    rsi_value = 0.0     # 当前RSI值
    
    # 必须明确告知系统哪些是参数，哪些是变量
    parameters = ["fast_window", "slow_window", "rsi_window", "fixed_size"]
    variables = ["fast_ma0", "slow_ma0", "rsi_value"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 创建K线生成器：默认由Tick合成1分钟K线
        # 如果需要合成15分钟，可以写: self.bg = BarGenerator(self.on_bar, 15, self.on_15min_bar)
        self.bg = BarGenerator(self.on_bar)
        
        # 创建K线数据容器：默认缓存100根K线，用于计算指标
        # 如果你的指标需要更长的数据（如MA200），这里要设大一点，例如 size=300
        self.am = ArrayManager(size=100)

    def on_init(self):
        """
        策略初始化回调
        """
        self.write_log("策略初始化")
        
        # 加载历史数据：用于填满 ArrayManager
        # 这里加载10天，确保有足够的K线计算出第一批 MA 指标
        self.load_bar(10)

    def on_start(self):
        """策略启动回调"""
        self.write_log("策略启动")

    def on_stop(self):
        """策略停止回调"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Tick数据更新
        实盘时每秒会有多次Tick推送，这里通常只做一件事：合成K线
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        K线数据更新 (核心逻辑都在这里)
        默认这是 1分钟 K线
        """
        # -----------------------------------------------------------------------------------
        # 第一步：推送数据到 ArrayManager 并检查是否初始化完成
        # -----------------------------------------------------------------------------------
        am = self.am
        am.update_bar(bar)
        
        # 如果缓存的K线数量还没达到 size (例如100根)，通过 load_bar 加载的历史数据不足，
        # 或者刚启动还没有攒够数据，直接返回，不计算指标也不交易
        if not am.inited:
            return

        # -----------------------------------------------------------------------------------
        # 第二步：计算技术指标
        # ArrayManager 内置了大量常用指标：sma, rsi, macd, boll, atr, kdj 等
        # array=True 表示获取一个数组（序列），False 表示只获取最新的一个值
        # -----------------------------------------------------------------------------------
        fast_ma = am.sma(self.fast_window, array=True)
        slow_ma = am.sma(self.slow_window, array=True)
        rsi_val = am.rsi(self.rsi_window) # 计算RSI
        
        # 更新变量，方便在界面查看
        self.fast_ma0 = fast_ma[-1]
        self.slow_ma0 = slow_ma[-1]
        self.rsi_value = rsi_val

        # ------------------------------------------------------------------------
        # 第三步：生成交易信号
        # [-1] 代表最新一根K线，[-2] 代表上一根K线
        # -----------------------------------------------------------------------------------
        # 金叉：快线上穿慢线
        cross_over = (fast_ma[-1] > slow_ma[-1]) and (fast_ma[-2] <= slow_ma[-2])
        
        # 死叉：快线下穿慢线
        cross_below = (fast_ma[-1] < slow_ma[-1]) and (fast_ma[-2] >= slow_ma[-2])

        # -----------------------------------------------------------------------------------
        # 第四步：执行交易逻辑
        # self.pos 是当前策略持仓（正数多头，负数空头，0空仓）
        # -----------------------------------------------------------------------------------
        
        # 如果发生了金叉，且RSI没有超买 (比如小于70)，才做多
        if cross_over and self.rsi_value < 70:
            # 价格：为了保证成交，买入价通常挂高一点 (bar.close_price + 5)
            # 仅仅是挂单价，实际成交价由撮合系统决定
            price = bar.close_price + 5
            
            if self.pos == 0:
                # 空仓 -> 买开
                self.buy(price, self.fixed_size)
            elif self.pos < 0:
                # 持有空单 -> 先平空单，再反手做多
                self.cover(price, self.fixed_size) # 买平
                self.buy(price, self.fixed_size)   # 买开

        # 如果发生了死叉，且RSI没有超卖 (比如大于30)，才做空
        elif cross_below and self.rsi_value > 30:
            price = bar.close_price - 5
            
            if self.pos == 0:
                # 空仓 -> 卖开
                self.short(price, self.fixed_size)
            elif self.pos > 0:
                # 持有多单 -> 先平多单，再反手做空
                self.sell(price, self.fixed_size)  # 卖平
                self.short(price, self.fixed_size) # 卖开

    def on_order(self, order: OrderData):
        """订单状态更新"""
        pass

    def on_trade(self, trade: TradeData):
        """成交信息更新"""
        # 成交后，立即把最新状态推送到界面
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """停止单更新"""
        pass
