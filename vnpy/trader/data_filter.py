"""
数据过滤模块

实现非交易时段垃圾数据过滤功能，根据品种交易时段配置文件，
自动过滤非交易时段的Tick数据。
参考Elite版数据过滤设计。
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, time
from collections import defaultdict

from .object import TickData, BarData
from .constant import Exchange, Product
from .logger import logger


# A股交易时段配置（上海/深圳交易所）
A_SHARE_TRADING_HOURS = {
    'morning_open': time(9, 30),   # 上午开盘
    'morning_close': time(11, 30),  # 上午收盘
    'afternoon_open': time(13, 0),  # 下午开盘
    'afternoon_close': time(15, 0), # 下午收盘
}

# 期货交易时段配置（示例：上期所）
FUTURES_TRADING_HOURS = {
    'night_open': time(21, 0),     # 夜盘开盘
    'night_close': time(2, 30),    # 夜盘收盘（次日）
    'morning_open': time(9, 0),     # 上午开盘
    'morning_close': time(11, 30), # 上午收盘
    'afternoon_open': time(13, 30), # 下午开盘
    'afternoon_close': time(15, 0), # 下午收盘
}

# 默认交易时段配置（按交易所）
DEFAULT_TRADING_HOURS: Dict[Exchange, Dict] = {
    Exchange.SSE: A_SHARE_TRADING_HOURS,      # 上海证券交易所（A股）
    Exchange.SZSE: A_SHARE_TRADING_HOURS,     # 深圳证券交易所（A股）
    Exchange.BSE: A_SHARE_TRADING_HOURS,      # 北京证券交易所（A股）
    Exchange.SHFE: FUTURES_TRADING_HOURS,     # 上海期货交易所
    Exchange.CZCE: FUTURES_TRADING_HOURS,      # 郑州商品交易所
    Exchange.DCE: FUTURES_TRADING_HOURS,      # 大连商品交易所
    Exchange.CFFEX: FUTURES_TRADING_HOURS,     # 中国金融期货交易所
    Exchange.INE: FUTURES_TRADING_HOURS,      # 上海国际能源交易中心
    Exchange.GFEX: FUTURES_TRADING_HOURS,     # 广州期货交易所
}


class DataFilter:
    """
    数据过滤器
    
    根据品种交易时段配置，自动过滤非交易时段的垃圾数据。
    """
    
    def __init__(self, trading_hours_config: Optional[Dict[Exchange, Dict]] = None):
        """
        初始化数据过滤器
        
        Args:
            trading_hours_config: 交易时段配置字典，None表示使用默认配置
        """
        self.trading_hours_config = trading_hours_config or DEFAULT_TRADING_HOURS
        
        # 过滤统计
        self.filter_stats: Dict[str, int] = defaultdict(int)
        
        logger.info("DataFilter初始化完成")
    
    def is_trading_time(self, dt: datetime, exchange: Exchange) -> bool:
        """
        判断指定时间是否为交易时段
        
        Args:
            dt: 时间
            exchange: 交易所
            
        Returns:
            bool: True表示是交易时段，False表示非交易时段
        """
        if exchange not in self.trading_hours_config:
            # 如果没有配置，默认不过滤
            logger.warning(f"交易所 {exchange} 未配置交易时段，不过滤数据")
            return True
        
        config = self.trading_hours_config[exchange]
        t = dt.time()
        
        # A股交易时段判断
        if 'morning_open' in config and 'afternoon_close' in config:
            morning_open = config['morning_open']
            morning_close = config['morning_close']
            afternoon_open = config['afternoon_open']
            afternoon_close = config['afternoon_close']
            
            # 上午时段：9:30 - 11:30
            if morning_open <= t <= morning_close:
                return True
            
            # 下午时段：13:00 - 15:00
            if afternoon_open <= t <= afternoon_close:
                return True
        
        # 期货交易时段判断（包含夜盘）
        if 'night_open' in config:
            night_open = config['night_open']
            night_close = config['night_close']
            morning_open = config.get('morning_open', time(9, 0))
            morning_close = config.get('morning_close', time(11, 30))
            afternoon_open = config.get('afternoon_open', time(13, 30))
            afternoon_close = config.get('afternoon_close', time(15, 0))
            
            # 夜盘时段：21:00 - 次日2:30
            if night_open <= t or t <= night_close:
                return True
            
            # 上午时段
            if morning_open <= t <= morning_close:
                return True
            
            # 下午时段
            if afternoon_open <= t <= afternoon_close:
                return True
        
        return False
    
    def filter_tick(self, tick: TickData) -> bool:
        """
        过滤Tick数据
        
        Args:
            tick: Tick数据
            
        Returns:
            bool: True表示保留，False表示过滤掉
        """
        if not tick.datetime:
            logger.warning("Tick数据缺少datetime，过滤掉")
            self.filter_stats['invalid_datetime'] += 1
            return False
        
        is_trading = self.is_trading_time(tick.datetime, tick.exchange)
        
        if not is_trading:
            self.filter_stats['non_trading_time'] += 1
            logger.debug(
                f"过滤非交易时段Tick: {tick.vt_symbol}, "
                f"{tick.datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        return is_trading
    
    def filter_bar(self, bar: BarData) -> bool:
        """
        过滤K线数据
        
        Args:
            bar: K线数据
            
        Returns:
            bool: True表示保留，False表示过滤掉
        """
        if not bar.datetime:
            logger.warning("K线数据缺少datetime，过滤掉")
            self.filter_stats['invalid_datetime'] += 1
            return False
        
        is_trading = self.is_trading_time(bar.datetime, bar.exchange)
        
        if not is_trading:
            self.filter_stats['non_trading_time'] += 1
            logger.debug(
                f"过滤非交易时段K线: {bar.vt_symbol}, "
                f"{bar.datetime.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        
        return is_trading
    
    def filter_ticks(self, ticks: List[TickData]) -> List[TickData]:
        """
        批量过滤Tick数据
        
        Args:
            ticks: Tick数据列表
            
        Returns:
            List[TickData]: 过滤后的Tick数据列表
        """
        filtered = [tick for tick in ticks if self.filter_tick(tick)]
        
        filtered_count = len(ticks) - len(filtered)
        if filtered_count > 0:
            logger.info(f"过滤了 {filtered_count}/{len(ticks)} 条非交易时段Tick数据")
        
        return filtered
    
    def filter_bars(self, bars: List[BarData]) -> List[BarData]:
        """
        批量过滤K线数据
        
        Args:
            bars: K线数据列表
            
        Returns:
            List[BarData]: 过滤后的K线数据列表
        """
        filtered = [bar for bar in bars if self.filter_bar(bar)]
        
        filtered_count = len(bars) - len(filtered)
        if filtered_count > 0:
            logger.info(f"过滤了 {filtered_count}/{len(bars)} 根非交易时段K线数据")
        
        return filtered
    
    def set_trading_hours(
        self,
        exchange: Exchange,
        trading_hours: Dict
    ) -> None:
        """
        设置指定交易所的交易时段
        
        Args:
            exchange: 交易所
            trading_hours: 交易时段配置字典
        """
        self.trading_hours_config[exchange] = trading_hours
        logger.info(f"设置交易所 {exchange} 的交易时段配置")
    
    def get_filter_stats(self) -> Dict[str, int]:
        """
        获取过滤统计信息
        
        Returns:
            Dict[str, int]: 过滤统计字典
        """
        return dict(self.filter_stats)
    
    def reset_stats(self) -> None:
        """重置过滤统计"""
        self.filter_stats.clear()
        logger.info("过滤统计已重置")


# 全局数据过滤器实例
_data_filter: Optional[DataFilter] = None


def get_data_filter() -> DataFilter:
    """
    获取全局数据过滤器实例
    
    Returns:
        DataFilter: 数据过滤器实例
    """
    global _data_filter
    if _data_filter is None:
        _data_filter = DataFilter()
    return _data_filter


def filter_tick_data(ticks: List[TickData]) -> List[TickData]:
    """
    过滤Tick数据的便捷函数
    
    Args:
        ticks: Tick数据列表
        
    Returns:
        List[TickData]: 过滤后的Tick数据列表
    """
    return get_data_filter().filter_ticks(ticks)


def filter_bar_data(bars: List[BarData]) -> List[BarData]:
    """
    过滤K线数据的便捷函数
    
    Args:
        bars: K线数据列表
        
    Returns:
        List[BarData]: 过滤后的K线数据列表
    """
    return get_data_filter().filter_bars(bars)
