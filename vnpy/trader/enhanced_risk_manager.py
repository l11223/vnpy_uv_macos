"""
增强型风险控制管理器

实现事前交易风控功能，包括委托速率限制、撤单比例监控、持仓限额检查等。
参考Elite版RiskManager设计，提供完善的事前交易风控。
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import time

from .object import OrderRequest, OrderData, TradeData, PositionData, AccountData
from .constant import Direction, Offset
from .logger import logger


class EnhancedRiskManager:
    """
    增强型风险控制管理器
    
    提供事前交易风控功能，包括：
    1. 委托速率限制
    2. 撤单比例监控
    3. 持仓限额检查
    4. 实时风险监控
    """
    
    def __init__(self, main_engine: Optional[object] = None):
        """
        初始化风险控制管理器
        
        Args:
            main_engine: 主引擎实例（可选）
        """
        self.main_engine = main_engine
        
        # 委托速率限制配置
        self.order_rate_limit: int = 10  # 每秒最大委托数
        self.order_rate_window: float = 1.0  # 时间窗口（秒）
        
        # 撤单比例限制配置
        self.cancel_ratio_limit: float = 0.5  # 最大撤单比例（50%）
        self.cancel_ratio_window: int = 100  # 统计窗口（最近N笔订单）
        
        # 持仓限额配置 {vt_symbol: max_position}
        self.position_limits: Dict[str, float] = {}
        
        # 委托记录（用于速率限制）
        self.order_timestamps: deque = deque(maxlen=1000)
        
        # 订单统计（用于撤单比例）
        self.order_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
            'total': 0,
            'cancelled': 0,
            'filled': 0
        })
        
        # 订单历史（最近N笔）
        self.recent_orders: deque = deque(maxlen=1000)
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 风控状态
        self.risk_enabled: bool = True
        self.blocked_symbols: set = set()  # 被风控阻止的合约
        
        logger.info("EnhancedRiskManager初始化完成")
    
    def check_order_rate(self, vt_symbol: str) -> tuple[bool, str]:
        """
        检查委托速率
        
        Args:
            vt_symbol: 合约代码
            
        Returns:
            tuple[bool, str]: (是否通过, 错误信息)
        """
        if not self.risk_enabled:
            return True, ""
        
        current_time = time.time()
        
        with self.lock:
            # 清理过期记录
            while self.order_timestamps and current_time - self.order_timestamps[0] > self.order_rate_window:
                self.order_timestamps.popleft()
            
            # 检查速率
            if len(self.order_timestamps) >= self.order_rate_limit:
                error_msg = f"委托速率超限: {len(self.order_timestamps)}/{self.order_rate_limit} (每秒)"
                logger.warning(error_msg)
                return False, error_msg
            
            # 记录本次委托时间
            self.order_timestamps.append(current_time)
        
        return True, ""
    
    def check_cancel_ratio(self, vt_symbol: str) -> tuple[bool, str]:
        """
        检查撤单比例
        
        Args:
            vt_symbol: 合约代码
            
        Returns:
            tuple[bool, str]: (是否通过, 错误信息)
        """
        if not self.risk_enabled:
            return True, ""
        
        with self.lock:
            stats = self.order_stats[vt_symbol]
            
            # 计算撤单比例
            total = stats['total']
            cancelled = stats['cancelled']
            
            if total == 0:
                return True, ""
            
            cancel_ratio = cancelled / total
            
            if cancel_ratio > self.cancel_ratio_limit:
                error_msg = (
                    f"撤单比例超限: {cancel_ratio:.2%} > {self.cancel_ratio_limit:.2%} "
                    f"({cancelled}/{total})"
                )
                logger.warning(error_msg)
                return False, error_msg
        
        return True, ""
    
    def check_position_limit(
        self,
        vt_symbol: str,
        order_volume: float,
        current_position: float
    ) -> tuple[bool, str]:
        """
        检查持仓限额
        
        Args:
            vt_symbol: 合约代码
            order_volume: 订单数量（正数买入，负数卖出）
            current_position: 当前持仓
            
        Returns:
            tuple[bool, str]: (是否通过, 错误信息)
        """
        if not self.risk_enabled:
            return True, ""
        
        if vt_symbol not in self.position_limits:
            return True, ""  # 未设置限额，不限制
        
        max_position = self.position_limits[vt_symbol]
        
        # 计算委托后的持仓
        new_position = current_position + order_volume
        
        if abs(new_position) > abs(max_position):
            error_msg = (
                f"持仓限额超限: {new_position:.2f} > {max_position:.2f} "
                f"(当前: {current_position:.2f}, 委托: {order_volume:.2f})"
            )
            logger.warning(error_msg)
            return False, error_msg
        
        return True, ""
    
    def check_order_request(
        self,
        req: OrderRequest,
        current_position: Optional[float] = None
    ) -> tuple[bool, str]:
        """
        检查订单请求（综合风控检查）
        
        Args:
            req: 订单请求
            current_position: 当前持仓（可选，如果不提供则从引擎获取）
            
        Returns:
            tuple[bool, str]: (是否通过, 错误信息)
        """
        if not self.risk_enabled:
            return True, ""
        
        vt_symbol = req.vt_symbol
        
        # 检查是否被阻止
        if vt_symbol in self.blocked_symbols:
            return False, f"合约 {vt_symbol} 已被风控阻止"
        
        # 1. 检查委托速率
        passed, error = self.check_order_rate(vt_symbol)
        if not passed:
            return False, error
        
        # 2. 检查撤单比例
        passed, error = self.check_cancel_ratio(vt_symbol)
        if not passed:
            return False, error
        
        # 3. 检查持仓限额
        if current_position is None:
            # 尝试从引擎获取
            if self.main_engine:
                position = self.main_engine.get_position(vt_symbol)
                if position:
                    current_position = position.volume if position.direction == Direction.LONG else -position.volume
                else:
                    current_position = 0.0
            else:
                current_position = 0.0
        
        # 计算订单数量（考虑方向）
        order_volume = req.volume
        if req.direction == Direction.SHORT:
            order_volume = -order_volume
        
        passed, error = self.check_position_limit(vt_symbol, order_volume, current_position)
        if not passed:
            return False, error
        
        return True, ""
    
    def record_order(self, order: OrderData) -> None:
        """
        记录订单（用于统计）
        
        Args:
            order: 订单数据
        """
        with self.lock:
            vt_symbol = order.vt_symbol
            self.order_stats[vt_symbol]['total'] += 1
            self.recent_orders.append({
                'vt_symbol': vt_symbol,
                'vt_orderid': order.vt_orderid,
                'datetime': order.datetime or datetime.now(),
                'status': order.status
            })
    
    def record_cancel(self, order: OrderData) -> None:
        """
        记录撤单（用于统计）
        
        Args:
            order: 订单数据
        """
        with self.lock:
            vt_symbol = order.vt_symbol
            self.order_stats[vt_symbol]['cancelled'] += 1
    
    def record_fill(self, trade: TradeData) -> None:
        """
        记录成交（用于统计）
        
        Args:
            trade: 成交数据
        """
        with self.lock:
            vt_symbol = trade.vt_symbol
            self.order_stats[vt_symbol]['filled'] += 1
    
    def set_order_rate_limit(self, limit: int, window: float = 1.0) -> None:
        """
        设置委托速率限制
        
        Args:
            limit: 每秒最大委托数
            window: 时间窗口（秒）
        """
        with self.lock:
            self.order_rate_limit = limit
            self.order_rate_window = window
            logger.info(f"设置委托速率限制: {limit} 笔/秒 (窗口: {window}秒)")
    
    def set_cancel_ratio_limit(self, limit: float, window: int = 100) -> None:
        """
        设置撤单比例限制
        
        Args:
            limit: 最大撤单比例（0-1之间）
            window: 统计窗口（最近N笔订单）
        """
        with self.lock:
            self.cancel_ratio_limit = limit
            self.cancel_ratio_window = window
            logger.info(f"设置撤单比例限制: {limit:.2%} (窗口: {window}笔)")
    
    def set_position_limit(self, vt_symbol: str, max_position: float) -> None:
        """
        设置持仓限额
        
        Args:
            vt_symbol: 合约代码
            max_position: 最大持仓（正数表示多头限额，负数表示空头限额）
        """
        with self.lock:
            self.position_limits[vt_symbol] = max_position
            logger.info(f"设置 {vt_symbol} 持仓限额: {max_position:.2f}")
    
    def remove_position_limit(self, vt_symbol: str) -> None:
        """
        移除持仓限额
        
        Args:
            vt_symbol: 合约代码
        """
        with self.lock:
            if vt_symbol in self.position_limits:
                del self.position_limits[vt_symbol]
                logger.info(f"移除 {vt_symbol} 持仓限额")
    
    def block_symbol(self, vt_symbol: str) -> None:
        """
        阻止指定合约的交易
        
        Args:
            vt_symbol: 合约代码
        """
        with self.lock:
            self.blocked_symbols.add(vt_symbol)
            logger.warning(f"风控阻止合约: {vt_symbol}")
    
    def unblock_symbol(self, vt_symbol: str) -> None:
        """
        解除指定合约的交易阻止
        
        Args:
            vt_symbol: 合约代码
        """
        with self.lock:
            if vt_symbol in self.blocked_symbols:
                self.blocked_symbols.remove(vt_symbol)
                logger.info(f"解除合约阻止: {vt_symbol}")
    
    def get_risk_stats(self, vt_symbol: Optional[str] = None) -> Dict:
        """
        获取风控统计信息
        
        Args:
            vt_symbol: 合约代码（None表示所有合约）
            
        Returns:
            Dict: 风控统计字典
        """
        with self.lock:
            if vt_symbol:
                stats = self.order_stats.get(vt_symbol, {})
                return {
                    'vt_symbol': vt_symbol,
                    'total_orders': stats.get('total', 0),
                    'cancelled_orders': stats.get('cancelled', 0),
                    'filled_orders': stats.get('filled', 0),
                    'cancel_ratio': stats.get('cancelled', 0) / max(stats.get('total', 1), 1),
                    'recent_order_rate': len(self.order_timestamps) / self.order_rate_window,
                    'is_blocked': vt_symbol in self.blocked_symbols
                }
            else:
                # 所有合约统计
                all_stats = {}
                for symbol in self.order_stats.keys():
                    all_stats[symbol] = self.get_risk_stats(symbol)
                return all_stats
    
    def reset_stats(self, vt_symbol: Optional[str] = None) -> None:
        """
        重置统计信息
        
        Args:
            vt_symbol: 合约代码（None表示所有合约）
        """
        with self.lock:
            if vt_symbol:
                if vt_symbol in self.order_stats:
                    self.order_stats[vt_symbol] = {'total': 0, 'cancelled': 0, 'filled': 0}
                    logger.info(f"重置 {vt_symbol} 风控统计")
            else:
                self.order_stats.clear()
                self.order_timestamps.clear()
                self.recent_orders.clear()
                logger.info("重置所有风控统计")
    
    def enable_risk_control(self) -> None:
        """启用风控"""
        self.risk_enabled = True
        logger.info("风控已启用")
    
    def disable_risk_control(self) -> None:
        """禁用风控"""
        self.risk_enabled = False
        logger.warning("风控已禁用")
    
    def get_config(self) -> Dict:
        """
        获取风控配置
        
        Returns:
            Dict: 配置字典
        """
        return {
            'risk_enabled': self.risk_enabled,
            'order_rate_limit': self.order_rate_limit,
            'order_rate_window': self.order_rate_window,
            'cancel_ratio_limit': self.cancel_ratio_limit,
            'cancel_ratio_window': self.cancel_ratio_window,
            'position_limits': dict(self.position_limits),
            'blocked_symbols': list(self.blocked_symbols)
        }
    
    def set_config(self, config: Dict) -> None:
        """
        设置风控配置
        
        Args:
            config: 配置字典
        """
        with self.lock:
            if 'risk_enabled' in config:
                self.risk_enabled = config['risk_enabled']
            if 'order_rate_limit' in config:
                self.order_rate_limit = config['order_rate_limit']
            if 'order_rate_window' in config:
                self.order_rate_window = config['order_rate_window']
            if 'cancel_ratio_limit' in config:
                self.cancel_ratio_limit = config['cancel_ratio_limit']
            if 'cancel_ratio_window' in config:
                self.cancel_ratio_window = config['cancel_ratio_window']
            if 'position_limits' in config:
                self.position_limits.update(config['position_limits'])
            if 'blocked_symbols' in config:
                self.blocked_symbols = set(config['blocked_symbols'])
            
            logger.info("风控配置已更新")
