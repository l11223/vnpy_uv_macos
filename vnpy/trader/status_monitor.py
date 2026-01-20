"""
实时状态监控模块

实现算法执行状态、持仓变动、运行日志的实时监控功能。
确保策略运行符合预期，参考Elite版状态监控设计。
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import time

from .object import OrderData, TradeData, PositionData, LogData
from .logger import logger


class StatusMonitor:
    """
    实时状态监控器
    
    监控算法执行状态、持仓变动、运行日志等，确保策略运行符合预期。
    """
    
    def __init__(self, main_engine: Optional[object] = None):
        """
        初始化状态监控器
        
        Args:
            main_engine: 主引擎实例（可选）
        """
        self.main_engine = main_engine
        
        # 策略状态监控 {strategy_name: status_dict}
        self.strategy_status: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # 持仓变动监控 {vt_symbol: position_history}
        self.position_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # 运行日志监控（最近N条）
        self.recent_logs: deque = deque(maxlen=1000)
        
        # 订单监控 {vt_symbol: order_list}
        self.recent_orders: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 成交监控 {vt_symbol: trade_list}
        self.recent_trades: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # 监控回调函数
        self.status_callbacks: List[Callable] = []
        self.position_callbacks: List[Callable] = []
        self.log_callbacks: List[Callable] = []
        
        # 线程锁
        self.lock = threading.RLock()
        
        # 监控状态
        self.monitoring: bool = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        logger.info("StatusMonitor初始化完成")
    
    def start_monitoring(self) -> None:
        """启动实时监控"""
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("实时状态监控已启动")
    
    def stop_monitoring(self) -> None:
        """停止实时监控"""
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
        logger.info("实时状态监控已停止")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        while self.monitoring:
            try:
                # 定期检查策略状态
                self._check_strategy_status()
                
                # 触发状态回调
                self._trigger_status_callbacks()
                
                time.sleep(1.0)  # 每秒检查一次
                
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                time.sleep(1.0)
    
    def _check_strategy_status(self) -> None:
        """检查策略状态"""
        # 这里可以检查策略是否正常运行
        # 例如：检查策略进程是否存活、是否有异常等
        pass
    
    def update_strategy_status(
        self,
        strategy_name: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        更新策略状态
        
        Args:
            strategy_name: 策略名称
            status: 状态（running, stopped, error等）
            details: 详细信息字典
        """
        with self.lock:
            self.strategy_status[strategy_name] = {
                'status': status,
                'update_time': datetime.now(),
                'details': details or {}
            }
            
            logger.debug(f"策略 {strategy_name} 状态更新: {status}")
    
    def record_position_change(
        self,
        vt_symbol: str,
        position: PositionData
    ) -> None:
        """
        记录持仓变动
        
        Args:
            vt_symbol: 合约代码
            position: 持仓数据
        """
        with self.lock:
            self.position_history[vt_symbol].append({
                'datetime': position.datetime or datetime.now(),
                'volume': position.volume,
                'direction': position.direction,
                'frozen': position.frozen,
                'price': position.price,
                'pnl': position.pnl
            })
            
            # 触发持仓变动回调
            for callback in self.position_callbacks:
                try:
                    callback(vt_symbol, position)
                except Exception as e:
                    logger.error(f"执行持仓变动回调失败: {e}")
    
    def record_order(self, order: OrderData) -> None:
        """
        记录订单
        
        Args:
            order: 订单数据
        """
        with self.lock:
            vt_symbol = order.vt_symbol
            self.recent_orders[vt_symbol].append({
                'datetime': order.datetime or datetime.now(),
                'vt_orderid': order.vt_orderid,
                'direction': order.direction,
                'offset': order.offset,
                'price': order.price,
                'volume': order.volume,
                'traded': order.traded,
                'status': order.status
            })
    
    def record_trade(self, trade: TradeData) -> None:
        """
        记录成交
        
        Args:
            trade: 成交数据
        """
        with self.lock:
            vt_symbol = trade.vt_symbol
            self.recent_trades[vt_symbol].append({
                'datetime': trade.datetime or datetime.now(),
                'vt_tradeid': trade.vt_tradeid,
                'direction': trade.direction,
                'offset': trade.offset,
                'price': trade.price,
                'volume': trade.volume
            })
    
    def record_log(self, log: LogData) -> None:
        """
        记录日志
        
        Args:
            log: 日志数据
        """
        with self.lock:
            self.recent_logs.append({
                'datetime': datetime.now(),
                'gateway_name': log.gateway_name,
                'msg': log.msg
            })
            
            # 触发日志回调
            for callback in self.log_callbacks:
                try:
                    callback(log)
                except Exception as e:
                    logger.error(f"执行日志回调失败: {e}")
    
    def get_strategy_status(self, strategy_name: Optional[str] = None) -> Dict:
        """
        获取策略状态
        
        Args:
            strategy_name: 策略名称（None表示所有策略）
            
        Returns:
            Dict: 策略状态字典
        """
        with self.lock:
            if strategy_name:
                return dict(self.strategy_status.get(strategy_name, {}))
            else:
                return {name: dict(status) for name, status in self.strategy_status.items()}
    
    def get_position_history(
        self,
        vt_symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """
        获取持仓变动历史
        
        Args:
            vt_symbol: 合约代码
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）
            
        Returns:
            List[Dict]: 持仓变动历史列表
        """
        with self.lock:
            history = list(self.position_history.get(vt_symbol, []))
            
            # 时间过滤
            if start_time:
                history = [h for h in history if h['datetime'] >= start_time]
            if end_time:
                history = [h for h in history if h['datetime'] <= end_time]
            
            return history
    
    def get_recent_orders(
        self,
        vt_symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取最近订单
        
        Args:
            vt_symbol: 合约代码（None表示所有合约）
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 订单列表
        """
        with self.lock:
            if vt_symbol:
                orders = list(self.recent_orders.get(vt_symbol, []))
            else:
                # 合并所有合约的订单
                orders = []
                for symbol_orders in self.recent_orders.values():
                    orders.extend(symbol_orders)
                # 按时间排序
                orders.sort(key=lambda x: x['datetime'], reverse=True)
            
            return orders[:limit]
    
    def get_recent_trades(
        self,
        vt_symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取最近成交
        
        Args:
            vt_symbol: 合约代码（None表示所有合约）
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 成交列表
        """
        with self.lock:
            if vt_symbol:
                trades = list(self.recent_trades.get(vt_symbol, []))
            else:
                # 合并所有合约的成交
                trades = []
                for symbol_trades in self.recent_trades.values():
                    trades.extend(symbol_trades)
                # 按时间排序
                trades.sort(key=lambda x: x['datetime'], reverse=True)
            
            return trades[:limit]
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        """
        获取最近日志
        
        Args:
            limit: 返回数量限制
            
        Returns:
            List[Dict]: 日志列表
        """
        with self.lock:
            return list(self.recent_logs)[-limit:]
    
    def register_status_callback(self, callback: Callable) -> None:
        """
        注册状态监控回调函数
        
        Args:
            callback: 回调函数，接收策略状态字典
        """
        with self.lock:
            if callback not in self.status_callbacks:
                self.status_callbacks.append(callback)
                logger.debug("注册状态监控回调")
    
    def register_position_callback(self, callback: Callable) -> None:
        """
        注册持仓变动回调函数
        
        Args:
            callback: 回调函数，接收(vt_symbol, position)参数
        """
        with self.lock:
            if callback not in self.position_callbacks:
                self.position_callbacks.append(callback)
                logger.debug("注册持仓变动回调")
    
    def register_log_callback(self, callback: Callable) -> None:
        """
        注册日志回调函数
        
        Args:
            callback: 回调函数，接收LogData参数
        """
        with self.lock:
            if callback not in self.log_callbacks:
                self.log_callbacks.append(callback)
                logger.debug("注册日志回调")
    
    def unregister_status_callback(self, callback: Callable) -> None:
        """取消注册状态监控回调"""
        with self.lock:
            if callback in self.status_callbacks:
                self.status_callbacks.remove(callback)
    
    def unregister_position_callback(self, callback: Callable) -> None:
        """取消注册持仓变动回调"""
        with self.lock:
            if callback in self.position_callbacks:
                self.position_callbacks.remove(callback)
    
    def unregister_log_callback(self, callback: Callable) -> None:
        """取消注册日志回调"""
        with self.lock:
            if callback in self.log_callbacks:
                self.log_callbacks.remove(callback)
    
    def _trigger_status_callbacks(self) -> None:
        """触发状态监控回调"""
        status = self.get_strategy_status()
        for callback in self.status_callbacks:
            try:
                callback(status)
            except Exception as e:
                logger.error(f"执行状态监控回调失败: {e}")
    
    def get_monitoring_summary(self) -> Dict:
        """
        获取监控摘要
        
        Returns:
            Dict: 监控摘要字典
        """
        with self.lock:
            summary = {
                'monitoring': self.monitoring,
                'strategy_count': len(self.strategy_status),
                'symbol_count': len(self.position_history),
                'total_orders': sum(len(orders) for orders in self.recent_orders.values()),
                'total_trades': sum(len(trades) for trades in self.recent_trades.values()),
                'total_logs': len(self.recent_logs),
                'callback_count': {
                    'status': len(self.status_callbacks),
                    'position': len(self.position_callbacks),
                    'log': len(self.log_callbacks)
                }
            }
            
            return summary
    
    def clear_history(self, vt_symbol: Optional[str] = None) -> None:
        """
        清除历史记录
        
        Args:
            vt_symbol: 合约代码（None表示所有合约）
        """
        with self.lock:
            if vt_symbol:
                if vt_symbol in self.position_history:
                    self.position_history[vt_symbol].clear()
                if vt_symbol in self.recent_orders:
                    self.recent_orders[vt_symbol].clear()
                if vt_symbol in self.recent_trades:
                    self.recent_trades[vt_symbol].clear()
                logger.info(f"清除 {vt_symbol} 的历史记录")
            else:
                self.position_history.clear()
                self.recent_orders.clear()
                self.recent_trades.clear()
                self.recent_logs.clear()
                logger.info("清除所有历史记录")
