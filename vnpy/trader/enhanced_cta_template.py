"""
增强型CTA策略模板基类

提供基于理论目标的持仓维护方案，解决回测与实盘不一致问题。
参考Elite版EliteCtaTemplate设计，实现目标仓位计算和维护逻辑。
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Dict, Optional, List, Callable
from datetime import datetime

from .object import BarData, TickData, OrderData, TradeData, PositionData
from .constant import Direction, Offset
from .logger import logger


class EnhancedCtaTemplate(ABC):
    """
    增强型CTA策略模板基类
    
    核心特性：
    1. 基于理论目标的持仓维护方案
    2. 目标仓位与实际仓位的自动对齐
    3. 支持历史行情回放计算策略状态
    4. 自动拆单执行逻辑
    """
    
    def __init__(
        self,
        cta_engine: Optional[object] = None,
        strategy_name: str = "",
        vt_symbol: str = "",
        setting: Optional[Dict] = None
    ):
        """
        初始化策略模板
        
        Args:
            cta_engine: CTA策略引擎（可选）
            strategy_name: 策略名称
            vt_symbol: 交易合约代码
            setting: 策略参数设置
        """
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        
        # 目标仓位和实际仓位
        self.target_pos: float = 0.0  # 目标仓位（理论值）
        self.current_pos: float = 0.0  # 当前实际仓位
        
        # 仓位历史记录（用于回放）
        self.pos_history: List[Dict] = []
        
        # 订单管理
        self.orders: Dict[str, OrderData] = {}
        self.active_orderids: set = set()
        
        # 历史行情数据（用于回放）
        self.history_bars: List[BarData] = []
        self.history_ticks: List[TickData] = []
        
        # 回放状态
        self.replay_mode: bool = False
        self.replay_index: int = 0
        
        # 自动拆单配置
        self.auto_split: bool = True  # 是否自动拆单
        self.max_order_volume: float = 100.0  # 单笔订单最大数量
        self.price_tolerance: float = 0.001  # 价格容忍度（0.1%）
        
        # 策略状态
        self.inited: bool = False
        self.trading: bool = False
        
        # 设置策略参数
        if setting:
            for key, value in setting.items():
                if hasattr(self, key):
                    setattr(self, key, value)
        
        logger.info(f"EnhancedCtaTemplate初始化完成: {strategy_name}")
    
    @abstractmethod
    def on_init(self) -> None:
        """
        策略初始化回调
        
        在策略启动时调用，用于初始化策略参数和状态。
        """
        pass
    
    @abstractmethod
    def on_start(self) -> None:
        """
        策略启动回调
        
        在策略启动时调用，用于启动策略逻辑。
        """
        pass
    
    @abstractmethod
    def on_stop(self) -> None:
        """
        策略停止回调
        
        在策略停止时调用，用于清理资源。
        """
        pass
    
    @abstractmethod
    def on_tick(self, tick: TickData) -> None:
        """
        Tick行情回调
        
        Args:
            tick: Tick行情数据
        """
        pass
    
    @abstractmethod
    def on_bar(self, bar: BarData) -> None:
        """
        K线回调
        
        Args:
            bar: K线数据
        """
        pass
    
    def on_order(self, order: OrderData) -> None:
        """
        订单回调（可选重写）
        
        Args:
            order: 订单数据
        """
        pass
    
    def on_trade(self, trade: TradeData) -> None:
        """
        成交回调（可选重写）
        
        Args:
            trade: 成交数据
        """
        pass
    
    def set_target_pos(self, target_pos: float) -> None:
        """
        设置目标仓位
        
        这是策略的核心接口，策略只需要设置目标仓位，
        系统会自动维护实际仓位向目标仓位对齐。
        
        Args:
            target_pos: 目标仓位（正数表示多头，负数表示空头）
        """
        old_target = self.target_pos
        self.target_pos = target_pos
        
        logger.debug(
            f"策略 {self.strategy_name} 设置目标仓位: {old_target} -> {target_pos}"
        )
        
        # 如果策略正在运行，立即执行仓位调整
        if self.trading:
            self._maintain_position()
    
    def get_target_pos(self) -> float:
        """
        获取目标仓位
        
        Returns:
            float: 目标仓位
        """
        return self.target_pos
    
    def get_current_pos(self) -> float:
        """
        获取当前实际仓位
        
        Returns:
            float: 当前实际仓位
        """
        return self.current_pos
    
    def get_pos_diff(self) -> float:
        """
        获取仓位差异（目标仓位 - 当前仓位）
        
        Returns:
            float: 仓位差异
        """
        return self.target_pos - self.current_pos
    
    def _maintain_position(self) -> None:
        """
        维护仓位：自动调整实际仓位向目标仓位对齐
        
        这是核心的仓位维护逻辑，会自动计算需要调整的仓位，
        并调用自动拆单功能执行交易。
        """
        pos_diff = self.get_pos_diff()
        
        # 如果差异很小，不需要调整
        if abs(pos_diff) < 0.01:
            return
        
        # 取消所有未完成订单
        self.cancel_all()
        
        # 计算需要调整的仓位
        if pos_diff > 0:
            # 需要增加仓位（买入）
            self._execute_buy(abs(pos_diff))
        elif pos_diff < 0:
            # 需要减少仓位（卖出）
            self._execute_sell(abs(pos_diff))
    
    def _execute_buy(self, volume: float) -> None:
        """
        执行买入操作（自动拆单）
        
        Args:
            volume: 需要买入的数量
        """
        if not self.auto_split or volume <= self.max_order_volume:
            # 不需要拆单或数量较小，直接下单
            self.buy(volume)
        else:
            # 需要拆单
            num_orders = int(volume / self.max_order_volume) + (1 if volume % self.max_order_volume > 0 else 0)
            remaining = volume
            
            for i in range(num_orders):
                order_volume = min(self.max_order_volume, remaining)
                if order_volume > 0:
                    self.buy(order_volume)
                    remaining -= order_volume
    
    def _execute_sell(self, volume: float) -> None:
        """
        执行卖出操作（自动拆单）
        
        Args:
            volume: 需要卖出的数量
        """
        if not self.auto_split or volume <= self.max_order_volume:
            # 不需要拆单或数量较小，直接下单
            self.sell(volume)
        else:
            # 需要拆单
            num_orders = int(volume / self.max_order_volume) + (1 if volume % self.max_order_volume > 0 else 0)
            remaining = volume
            
            for i in range(num_orders):
                order_volume = min(self.max_order_volume, remaining)
                if order_volume > 0:
                    self.sell(order_volume)
                    remaining -= order_volume
    
    def buy(self, volume: float, price: Optional[float] = None, stop: bool = False) -> List[str]:
        """
        买入开仓
        
        Args:
            volume: 买入数量
            price: 买入价格（None表示市价）
            stop: 是否为止损单
            
        Returns:
            List[str]: 订单ID列表
        """
        if self.cta_engine:
            return self.cta_engine.buy(self, price or 0, volume, stop)
        else:
            logger.warning("CTA引擎未设置，无法执行买入操作")
            return []
    
    def sell(self, volume: float, price: Optional[float] = None, stop: bool = False) -> List[str]:
        """
        卖出平仓
        
        Args:
            volume: 卖出数量
            price: 卖出价格（None表示市价）
            stop: 是否为止损单
            
        Returns:
            List[str]: 订单ID列表
        """
        if self.cta_engine:
            return self.cta_engine.sell(self, price or 0, volume, stop)
        else:
            logger.warning("CTA引擎未设置，无法执行卖出操作")
            return []
    
    def short(self, volume: float, price: Optional[float] = None, stop: bool = False) -> List[str]:
        """
        卖出开仓（做空）
        
        Args:
            volume: 卖出数量
            price: 卖出价格（None表示市价）
            stop: 是否为止损单
            
        Returns:
            List[str]: 订单ID列表
        """
        if self.cta_engine:
            return self.cta_engine.short(self, price or 0, volume, stop)
        else:
            logger.warning("CTA引擎未设置，无法执行做空操作")
            return []
    
    def cover(self, volume: float, price: Optional[float] = None, stop: bool = False) -> List[str]:
        """
        买入平仓（平空）
        
        Args:
            volume: 买入数量
            price: 买入价格（None表示市价）
            stop: 是否为止损单
            
        Returns:
            List[str]: 订单ID列表
        """
        if self.cta_engine:
            return self.cta_engine.cover(self, price or 0, volume, stop)
        else:
            logger.warning("CTA引擎未设置，无法执行平仓操作")
            return []
    
    def cancel_order(self, vt_orderid: str) -> None:
        """
        撤销订单
        
        Args:
            vt_orderid: 订单ID
        """
        if self.cta_engine:
            self.cta_engine.cancel_order(self, vt_orderid)
        else:
            logger.warning("CTA引擎未设置，无法撤销订单")
    
    def cancel_all(self) -> None:
        """撤销所有未完成订单"""
        for vt_orderid in list(self.active_orderids):
            self.cancel_order(vt_orderid)
    
    def update_order(self, order: OrderData) -> None:
        """
        更新订单状态
        
        Args:
            order: 订单数据
        """
        self.orders[order.vt_orderid] = order
        
        if not order.is_active() and order.vt_orderid in self.active_orderids:
            self.active_orderids.remove(order.vt_orderid)
        
        self.on_order(order)
    
    def update_trade(self, trade: TradeData) -> None:
        """
        更新成交数据
        
        Args:
            trade: 成交数据
        """
        # 更新实际仓位
        if trade.direction == Direction.LONG:
            self.current_pos += trade.volume
        else:
            self.current_pos -= trade.volume
        
        # 记录仓位历史
        self.pos_history.append({
            'datetime': trade.datetime,
            'target_pos': self.target_pos,
            'current_pos': self.current_pos,
            'trade': trade
        })
        
        self.on_trade(trade)
    
    def update_position(self, position: PositionData) -> None:
        """
        更新持仓数据
        
        Args:
            position: 持仓数据
        """
        if position.direction == Direction.LONG:
            self.current_pos = position.volume
        elif position.direction == Direction.SHORT:
            self.current_pos = -position.volume
        else:
            self.current_pos = position.volume
    
    def write_log(self, msg: str) -> None:
        """
        输出日志
        
        Args:
            msg: 日志消息
        """
        if self.cta_engine:
            self.cta_engine.write_log(msg, self)
        else:
            logger.info(f"[{self.strategy_name}] {msg}")
    
    def load_bar(
        self,
        days: int,
        interval: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> List[BarData]:
        """
        加载历史K线数据
        
        Args:
            days: 加载天数
            interval: K线周期（如"1m", "5m", "1d"）
            callback: 回调函数（用于回放）
            
        Returns:
            List[BarData]: 历史K线数据列表
        """
        if self.cta_engine:
            bars = self.cta_engine.load_bar(
                self.vt_symbol,
                days,
                interval or "1m"
            )
            
            if callback:
                # 如果提供了回调函数，执行回放
                self.replay_bars(bars, callback)
            
            return bars
        else:
            logger.warning("CTA引擎未设置，无法加载历史数据")
            return []
    
    def replay_bars(self, bars: List[BarData], callback: Callable) -> None:
        """
        回放历史K线数据
        
        按时间顺序回放历史数据，计算策略状态，确保策略状态完全基于历史行情。
        
        Args:
            bars: 历史K线数据列表
            callback: 回调函数，接收BarData参数
        """
        self.replay_mode = True
        self.replay_index = 0
        self.history_bars = sorted(bars, key=lambda x: x.datetime)
        
        logger.info(f"开始回放 {len(self.history_bars)} 根K线数据")
        
        # 重置策略状态
        self.current_pos = 0.0
        self.target_pos = 0.0
        self.pos_history = []
        
        # 按时间顺序回放
        for bar in self.history_bars:
            self.replay_index += 1
            callback(bar)
        
        self.replay_mode = False
        logger.info("历史K线回放完成")
    
    def get_parameters(self) -> Dict:
        """
        获取策略参数
        
        Returns:
            Dict: 策略参数字典
        """
        params = {}
        for key in dir(self):
            if not key.startswith('_') and not callable(getattr(self, key, None)):
                try:
                    value = getattr(self, key)
                    if isinstance(value, (int, float, str, bool, list, dict)):
                        params[key] = value
                except:
                    pass
        return params
    
    def set_parameters(self, params: Dict) -> None:
        """
        设置策略参数
        
        Args:
            params: 策略参数字典
        """
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
