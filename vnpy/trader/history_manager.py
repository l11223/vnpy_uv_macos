"""
历史数据管理器组件

提供自动化K线缓存功能，支持on_history回调函数，快速生成DataFrame对象。
参考Elite版HistoryManager设计，优化数据访问性能。
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from .object import BarData, TickData
from .constant import Interval, Exchange
from .database import get_database, BaseDatabase
from .logger import logger

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    logger.warning("pandas未安装，HistoryManager的DataFrame功能将不可用")


class HistoryManager:
    """
    历史数据管理器
    
    提供自动化K线缓存、快速数据访问和DataFrame生成功能。
    支持on_history回调函数，当新数据加载时自动触发回调。
    """
    
    def __init__(self, database: Optional[BaseDatabase] = None):
        """
        初始化历史数据管理器
        
        Args:
            database: 数据库实例，None表示使用默认数据库
        """
        self.database = database or get_database()
        
        # K线数据缓存 {vt_symbol: {interval: [BarData]}}
        self.bar_cache: Dict[str, Dict[str, List[BarData]]] = defaultdict(dict)
        
        # Tick数据缓存 {vt_symbol: [TickData]}
        self.tick_cache: Dict[str, List[TickData]] = defaultdict(list)
        
        # 缓存锁（线程安全）
        self.cache_lock = threading.RLock()
        
        # on_history回调函数 {vt_symbol: {interval: [Callable]}}
        self.history_callbacks: Dict[str, Dict[str, List[Callable]]] = defaultdict(lambda: defaultdict(list))
        
        # 缓存统计
        self.cache_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        logger.info("HistoryManager初始化完成")
    
    def load_bar_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
        callback: Optional[Callable] = None
    ) -> List[BarData]:
        """
        加载K线数据（带缓存）
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: K线周期
            start: 开始时间
            end: 结束时间
            callback: 数据加载完成后的回调函数
            
        Returns:
            List[BarData]: K线数据列表
        """
        vt_symbol = f"{symbol}.{exchange.value}"
        interval_str = interval.value if hasattr(interval, 'value') else str(interval)
        
        # 检查缓存
        cache_key = f"{vt_symbol}_{interval_str}"
        cached_bars = self._get_cached_bars(vt_symbol, interval_str, start, end)
        
        if cached_bars and len(cached_bars) > 0:
            logger.debug(f"从缓存加载 {len(cached_bars)} 根K线: {cache_key}")
            self.cache_stats[vt_symbol][interval_str] += 1
            
            # 触发回调
            if callback:
                callback(cached_bars)
            self._trigger_history_callbacks(vt_symbol, interval_str, cached_bars)
            
            return cached_bars
        
        # 从数据库加载
        logger.info(f"从数据库加载K线数据: {vt_symbol}, {interval_str}, {start} ~ {end}")
        bars = self.database.load_bar_data(symbol, exchange, interval, start, end)
        
        if bars:
            # 更新缓存
            with self.cache_lock:
                if interval_str not in self.bar_cache[vt_symbol]:
                    self.bar_cache[vt_symbol][interval_str] = []
                
                # 合并并去重
                existing_bars = self.bar_cache[vt_symbol][interval_str]
                existing_datetimes = {bar.datetime for bar in existing_bars}
                
                new_bars = [bar for bar in bars if bar.datetime not in existing_datetimes]
                self.bar_cache[vt_symbol][interval_str].extend(new_bars)
                
                # 按时间排序
                self.bar_cache[vt_symbol][interval_str].sort(key=lambda x: x.datetime)
            
            logger.info(f"加载完成，缓存 {len(self.bar_cache[vt_symbol][interval_str])} 根K线")
            
            # 触发回调
            if callback:
                callback(bars)
            self._trigger_history_callbacks(vt_symbol, interval_str, bars)
        
        return bars
    
    def load_tick_data(
        self,
        symbol: str,
        exchange: Exchange,
        start: datetime,
        end: datetime,
        callback: Optional[Callable] = None
    ) -> List[TickData]:
        """
        加载Tick数据（带缓存）
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            start: 开始时间
            end: 结束时间
            callback: 数据加载完成后的回调函数
            
        Returns:
            List[TickData]: Tick数据列表
        """
        vt_symbol = f"{symbol}.{exchange.value}"
        
        # 检查缓存
        cached_ticks = self._get_cached_ticks(vt_symbol, start, end)
        
        if cached_ticks and len(cached_ticks) > 0:
            logger.debug(f"从缓存加载 {len(cached_ticks)} 条Tick: {vt_symbol}")
            self.cache_stats[vt_symbol]['tick'] += 1
            
            # 触发回调
            if callback:
                callback(cached_ticks)
            
            return cached_ticks
        
        # 从数据库加载
        logger.info(f"从数据库加载Tick数据: {vt_symbol}, {start} ~ {end}")
        ticks = self.database.load_tick_data(symbol, exchange, start, end)
        
        if ticks:
            # 更新缓存
            with self.cache_lock:
                existing_ticks = self.tick_cache[vt_symbol]
                existing_datetimes = {tick.datetime for tick in existing_ticks}
                
                new_ticks = [tick for tick in ticks if tick.datetime not in existing_datetimes]
                self.tick_cache[vt_symbol].extend(new_ticks)
                
                # 按时间排序
                self.tick_cache[vt_symbol].sort(key=lambda x: x.datetime)
            
            logger.info(f"加载完成，缓存 {len(self.tick_cache[vt_symbol])} 条Tick")
            
            # 触发回调
            if callback:
                callback(ticks)
        
        return ticks
    
    def get_bar_dataframe(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Optional['pd.DataFrame']:
        """
        获取K线DataFrame对象
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: K线周期
            start: 开始时间（None表示从缓存最早时间开始）
            end: 结束时间（None表示到缓存最晚时间）
            
        Returns:
            Optional[pd.DataFrame]: K线DataFrame，如果pandas未安装则返回None
        """
        if not HAS_PANDAS:
            logger.warning("pandas未安装，无法生成DataFrame")
            return None
        
        vt_symbol = f"{symbol}.{exchange.value}"
        interval_str = interval.value if hasattr(interval, 'value') else str(interval)
        
        # 从缓存获取数据
        with self.cache_lock:
            if interval_str not in self.bar_cache[vt_symbol]:
                logger.warning(f"缓存中无数据: {vt_symbol}, {interval_str}")
                return None
            
            bars = self.bar_cache[vt_symbol][interval_str].copy()
        
        # 时间过滤
        if start:
            bars = [bar for bar in bars if bar.datetime >= start]
        if end:
            bars = [bar for bar in bars if bar.datetime <= end]
        
        if not bars:
            logger.warning(f"过滤后无数据: {vt_symbol}, {interval_str}")
            return None
        
        # 转换为DataFrame
        data = []
        for bar in bars:
            data.append({
                'datetime': bar.datetime,
                'open': bar.open_price,
                'high': bar.high_price,
                'low': bar.low_price,
                'close': bar.close_price,
                'volume': bar.volume,
                'turnover': bar.turnover,
                'open_interest': bar.open_interest
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        
        logger.debug(f"生成DataFrame: {len(df)} 行, {vt_symbol}, {interval_str}")
        return df
    
    def get_tick_dataframe(
        self,
        symbol: str,
        exchange: Exchange,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> Optional['pd.DataFrame']:
        """
        获取Tick DataFrame对象
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            start: 开始时间（None表示从缓存最早时间开始）
            end: 结束时间（None表示到缓存最晚时间）
            
        Returns:
            Optional[pd.DataFrame]: Tick DataFrame，如果pandas未安装则返回None
        """
        if not HAS_PANDAS:
            logger.warning("pandas未安装，无法生成DataFrame")
            return None
        
        vt_symbol = f"{symbol}.{exchange.value}"
        
        # 从缓存获取数据
        with self.cache_lock:
            if vt_symbol not in self.tick_cache:
                logger.warning(f"缓存中无Tick数据: {vt_symbol}")
                return None
            
            ticks = self.tick_cache[vt_symbol].copy()
        
        # 时间过滤
        if start:
            ticks = [tick for tick in ticks if tick.datetime >= start]
        if end:
            ticks = [tick for tick in ticks if tick.datetime <= end]
        
        if not ticks:
            logger.warning(f"过滤后无Tick数据: {vt_symbol}")
            return None
        
        # 转换为DataFrame
        data = []
        for tick in ticks:
            data.append({
                'datetime': tick.datetime,
                'last_price': tick.last_price,
                'volume': tick.volume,
                'turnover': tick.turnover,
                'open_interest': tick.open_interest,
                'bid_price_1': tick.bid_price_1,
                'ask_price_1': tick.ask_price_1,
                'bid_volume_1': tick.bid_volume_1,
                'ask_volume_1': tick.ask_volume_1
            })
        
        df = pd.DataFrame(data)
        df.set_index('datetime', inplace=True)
        
        logger.debug(f"生成Tick DataFrame: {len(df)} 行, {vt_symbol}")
        return df
    
    def register_history_callback(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        callback: Callable
    ) -> None:
        """
        注册历史数据回调函数
        
        当新数据加载到缓存时，会自动触发回调函数。
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: K线周期
            callback: 回调函数，接收List[BarData]参数
        """
        vt_symbol = f"{symbol}.{exchange.value}"
        interval_str = interval.value if hasattr(interval, 'value') else str(interval)
        
        with self.cache_lock:
            if callback not in self.history_callbacks[vt_symbol][interval_str]:
                self.history_callbacks[vt_symbol][interval_str].append(callback)
                logger.debug(f"注册历史数据回调: {vt_symbol}, {interval_str}")
    
    def unregister_history_callback(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        callback: Callable
    ) -> None:
        """
        取消注册历史数据回调函数
        
        Args:
            symbol: 合约代码
            exchange: 交易所
            interval: K线周期
            callback: 回调函数
        """
        vt_symbol = f"{symbol}.{exchange.value}"
        interval_str = interval.value if hasattr(interval, 'value') else str(interval)
        
        with self.cache_lock:
            if callback in self.history_callbacks[vt_symbol][interval_str]:
                self.history_callbacks[vt_symbol][interval_str].remove(callback)
                logger.debug(f"取消注册历史数据回调: {vt_symbol}, {interval_str}")
    
    def clear_cache(
        self,
        symbol: Optional[str] = None,
        exchange: Optional[Exchange] = None,
        interval: Optional[Interval] = None
    ) -> None:
        """
        清除缓存
        
        Args:
            symbol: 合约代码（None表示清除所有）
            exchange: 交易所（None表示清除所有）
            interval: K线周期（None表示清除所有周期）
        """
        with self.cache_lock:
            if symbol and exchange:
                vt_symbol = f"{symbol}.{exchange.value}"
                
                if interval:
                    interval_str = interval.value if hasattr(interval, 'value') else str(interval)
                    if interval_str in self.bar_cache[vt_symbol]:
                        del self.bar_cache[vt_symbol][interval_str]
                        logger.info(f"清除缓存: {vt_symbol}, {interval_str}")
                else:
                    # 清除该合约的所有周期
                    if vt_symbol in self.bar_cache:
                        del self.bar_cache[vt_symbol]
                    if vt_symbol in self.tick_cache:
                        del self.tick_cache[vt_symbol]
                    logger.info(f"清除缓存: {vt_symbol} (所有周期)")
            else:
                # 清除所有缓存
                self.bar_cache.clear()
                self.tick_cache.clear()
                logger.info("清除所有缓存")
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存信息
        
        Returns:
            Dict: 缓存统计信息
        """
        info = {
            'bar_cache': {},
            'tick_cache': {},
            'stats': dict(self.cache_stats)
        }
        
        with self.cache_lock:
            for vt_symbol, intervals in self.bar_cache.items():
                info['bar_cache'][vt_symbol] = {}
                for interval_str, bars in intervals.items():
                    info['bar_cache'][vt_symbol][interval_str] = len(bars)
                    if bars:
                        info['bar_cache'][vt_symbol][f"{interval_str}_start"] = bars[0].datetime.isoformat()
                        info['bar_cache'][vt_symbol][f"{interval_str}_end"] = bars[-1].datetime.isoformat()
            
            for vt_symbol, ticks in self.tick_cache.items():
                info['tick_cache'][vt_symbol] = len(ticks)
                if ticks:
                    info['tick_cache'][f"{vt_symbol}_start"] = ticks[0].datetime.isoformat()
                    info['tick_cache'][f"{vt_symbol}_end"] = ticks[-1].datetime.isoformat()
        
        return info
    
    def _get_cached_bars(
        self,
        vt_symbol: str,
        interval_str: str,
        start: datetime,
        end: datetime
    ) -> List[BarData]:
        """
        从缓存获取K线数据
        
        Args:
            vt_symbol: 合约代码
            interval_str: K线周期字符串
            start: 开始时间
            end: 结束时间
            
        Returns:
            List[BarData]: 缓存的K线数据列表
        """
        with self.cache_lock:
            if interval_str not in self.bar_cache[vt_symbol]:
                return []
            
            bars = self.bar_cache[vt_symbol][interval_str]
            
            # 时间过滤
            cached_bars = [
                bar for bar in bars
                if start <= bar.datetime <= end
            ]
            
            return cached_bars
    
    def _get_cached_ticks(
        self,
        vt_symbol: str,
        start: datetime,
        end: datetime
    ) -> List[TickData]:
        """
        从缓存获取Tick数据
        
        Args:
            vt_symbol: 合约代码
            start: 开始时间
            end: 结束时间
            
        Returns:
            List[TickData]: 缓存的Tick数据列表
        """
        with self.cache_lock:
            if vt_symbol not in self.tick_cache:
                return []
            
            ticks = self.tick_cache[vt_symbol]
            
            # 时间过滤
            cached_ticks = [
                tick for tick in ticks
                if start <= tick.datetime <= end
            ]
            
            return cached_ticks
    
    def _trigger_history_callbacks(
        self,
        vt_symbol: str,
        interval_str: str,
        bars: List[BarData]
    ) -> None:
        """
        触发历史数据回调函数
        
        Args:
            vt_symbol: 合约代码
            interval_str: K线周期字符串
            bars: 新加载的K线数据
        """
        if not bars:
            return
        
        callbacks = self.history_callbacks.get(vt_symbol, {}).get(interval_str, [])
        
        for callback in callbacks:
            try:
                callback(bars)
            except Exception as e:
                logger.error(f"执行历史数据回调函数失败: {e}")
