from typing import List, Optional, Tuple
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from mootdx.reader import Reader
from mootdx.quotes import Quotes
from collections.abc import Callable
from vnpy.trader.object import BarData, TickData, HistoryRequest
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.datafeed import BaseDatafeed
from vnpy.trader.setting import SETTINGS
from vnpy.trader.utility import is_trading_day, sync_holidays_cache

# 交易所映射
EXCHANGE_VT2TS: dict[Exchange, str] = {
    Exchange.CFFEX: "CFX",
    Exchange.SHFE: "SHF",
    Exchange.CZCE: "ZCE",
    Exchange.DCE: "DCE",
    Exchange.INE: "INE",
    Exchange.SSE: "SH",
    Exchange.SZSE: "SZ",
    Exchange.BSE: "BJ",
    Exchange.GFEX: "GFE"
}

def to_ts_symbol(symbol: str, exchange: Exchange) -> str | None:
    """将交易所代码转换为tushare代码"""
    # 股票
    if exchange in EXCHANGE_VT2TS:
        return  f"{symbol}.{EXCHANGE_VT2TS[exchange]}"

    return ""

class TdxDatafeed(BaseDatafeed):
    """
    TDX 离线数据获取模块
    """

    def __init__(self):
        """
        初始化
        """
        super().__init__()
        # sync_holidays_cache()
        # self.reader = Reader.factory(
        #     market='std',
        #     tdxdir=SETTINGS["datafeed.username"]
        # )
        self.client = Quotes.factory(
            market='std'
        )
        # ts.set_token(SETTINGS["datafeed.password"])
        self.trading_hours_per_day = 4  # 每天4小时交易时间
        self.trading_minutes_per_day = self.trading_hours_per_day * 60  # 每天240分钟交易时间
# 获取最后一个交易日
        try:
            df = self.client.bars(symbol="000001", frequency=4, offset=1, adjust='qfq')
            if not df.empty:
                datetime_str = df.iloc[0]['datetime']
                if isinstance(datetime_str, str):
                    self.last_trading_day = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M").replace(hour=15, minute=0)
                else:
                    self.last_trading_day = datetime_str.replace(hour=15, minute=0)
            else:
                raise ValueError("DataFrame is empty")
        except Exception as e:
            print(f"获取最后一个交易日失败: {e}, 使用当前日期作为默认值")
            self.last_trading_day = datetime.now().replace(hour=15, minute=0)

        self.morning_start = time(9, 30)
        self.morning_end = time(11, 30)
        self.afternoon_start = time(13, 0)
        self.afternoon_end = time(15, 0)
        print("TdxDatafeed init")
        
    @staticmethod
    def _get_week_info(dt: datetime) -> tuple:
        """
        获取日期所在的周数和该周的周五
        :param dt: 输入的日期
        :return: (周数, 周五的日期)
        """
        year, week_num, weekday = dt.isocalendar()
        friday = dt + timedelta(days=(5 - weekday))  # 5 对应周五（ISO标准中周一是1，周日是7）
        return week_num, friday.date()
    
    def _hm_to_offset(self) -> tuple:
        """
        根据当前时间计算小时偏移量和分钟偏移量。
        
        返回:
            tuple: 包含两个元素的元组：
                - hour_offset (int): 根据当前小时计算的小时偏移量。
                - minute_offset (int): 根据小时偏移量和当前分钟计算的分钟偏移量。
        
        """
        now = datetime.now().time()
        hour = now.hour
        minute = now.minute
        hour_offset = 0
        minute_offset = 0
        if hour < 11:
            hour_offset = 1
        elif hour < 13:
            hour_offset = 2
        elif hour >=14:
            hour_offset = 4
        elif hour >= 13:
            hour_offset = 3 
        if self.morning_start <= now <= self.morning_end:
            minute_offset = (now.hour - self.morning_start.hour) * 60 
            + (now.minute - self.morning_start.minute)
        elif self.afternoon_start <= now <= self.afternoon_end:
            minute_offset = (now.hour - self.afternoon_start.hour) * 60  
            + (now.minute - self.afternoon_start.minute) + 120
        else:
            minute_offset = hour_offset * 60
        return hour_offset, minute_offset
    
    def _date_to_offset(self, date: datetime, interval: Interval) -> int:
        """
        将日期转换为client.bars所需的偏移量（整数），仅计算交易日
        :param date: 目标日期
        :return: 距离最后一个交易日的交易日偏移量（0=最后一天，1=前一天）
        """
        target_date = date.date()
        target_hour = date.hour
        target_minute = date.minute
        if interval == Interval.WEEKLY:
            wn,friday = TdxDatafeed._get_week_info(date)
            target_date = friday
            target_hour = 0
            target_minute = 0
        
        if target_date > self.last_trading_day.date():
            return 0  # 未来日期视为当天
        elif target_date == self.last_trading_day.date():
            if interval == Interval.HOUR:
                if target_hour >= 15:
                    return 0
        offset = 0
        current_date = self.last_trading_day.date()
        if interval == Interval.DAILY:
            while current_date > target_date:
                if is_trading_day(current_date):
                    offset += 1
                current_date -= timedelta(days=1)
        elif interval == Interval.WEEKLY:
            wn, current_date = TdxDatafeed._get_week_info(self.last_trading_day)
            while current_date > target_date:
                if is_trading_day(current_date):
                    offset += 1
                else:
                    find_date = current_date
                    for i in range(0, 4):
                        find_date -= timedelta(days=1)
                        if is_trading_day(find_date):
                            offset += 1
                            # print(f"find_date: {find_date}", current_date)
                            break
                current_date -= timedelta(weeks=1)
        else:

            while current_date >= target_date:
                if is_trading_day(current_date):
                    offset += 1
                current_date -= timedelta(days=1)
            if interval == Interval.HOUR:
                offset *= self.trading_hours_per_day
                if is_trading_day(self.last_trading_day):
                    hour_offset = self._hm_to_offset()[0]
                    offset -= self.trading_hours_per_day - hour_offset
                if target_hour >= 15:
                    offset -= self.trading_hours_per_day
                elif target_hour >= 14:
                    offset -= 3
                elif target_hour >= 12:
                    offset -= 2
                elif target_hour >= 10:
                    offset -= 1
            elif interval == Interval.MINUTE:
                offset *= self.trading_minutes_per_day
                if is_trading_day(self.last_trading_day):
                    minute_offset = self._hm_to_offset()[1]
                    offset -= self.trading_minutes_per_day - minute_offset
                if target_hour >= 15:
                    offset -= self.trading_minutes_per_day
                elif target_hour >= 14:
                    offset = offset - 180 - target_minute
                elif target_hour >= 12:
                    offset = offset - 120 - target_minute
                elif target_hour >= 10:
                    offset = offset - 60 - target_minute
            else:
                raise ValueError("不支持的分钟间隔")
        return offset


    def _convert_df_to_bars(self, df, symbol, exchange, interval):
        """将DataFrame转换为BarData列表"""
        bars = []
        for _, row in df.iterrows():
            dt = row.name
            dt = dt.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
            dt = dt.to_pydatetime()
            bars.append(BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=dt,
                interval=interval,
                open_price=row["open"],
                high_price=row["high"],
                low_price=row["low"],
                close_price=row["close"],
                volume=row["volume"],
                open_interest=0,
                gateway_name="TDX"
            ))
        return bars

    def split_date_range(self, start: datetime, end: datetime, interval: Interval,max_offset: int = 800) -> List[Tuple[int, int]]:
        """
        分割日期范围为偏移量范围列表（支持分钟、小时和日线）
        :param start: 开始日期
        :param end: 结束日期
        :param interval: K线周期（分钟、小时或日线）
        :param max_offset: 每个子范围的最大偏移量（默认800）
        :return: 偏移量范围列表，如 [(0, 799), (800, 100)]
        """
        start_offset = self._date_to_offset(end, interval)   # end是更早的日期
        end_offset = self._date_to_offset(start, interval)   # start是更晚的日期
        total_offset = end_offset - start_offset
        if interval == Interval.DAILY or interval == Interval.WEEKLY:
            total_offset += 1
        # else:
        #     dt = self.last_trading_day.replace(hour=start.hour, minute=start.minute)
        #     dt_offset = self._date_to_offset(dt, interval)
        #     total_offset += dt_offset
        if total_offset <= 0 :
            return []
        ranges = []
        current_offset = start_offset
        current_range = total_offset
        while total_offset > 0:
            current_range = min(current_range, max_offset)
            ranges.append((current_offset, current_range))
            total_offset -= current_range
            current_offset += current_range
            current_range = total_offset
        return ranges

    def query_bar_history(
        self,
        req: HistoryRequest,
        output: Callable = print
    ) -> Optional[List[BarData]]:
        """
        获取历史K线数据
        :param req: 历史数据请求对象
        :return: K线数据列表
        """
        # print("query bar history", req.symbol, req.exchange, req.interval, req.start, req.end)
        # 实现从 TDX 离线数据获取 K 线数据的逻辑
        return self.get_bars(
            req.symbol,
            req.exchange,
            req.interval,
            req.start,
            req.end,
            output = print
        )
    def query_tick_history(self, 
                           req: HistoryRequest, 
                           output: Callable = print
    ) -> list[TickData]:
        """
        Query history tick data.
        """
        #东财数据
        # df = ts.realtime_tick(ts_code=to_ts_symbol(req.symbol, req.exchange),src='dc')
        now = datetime.now()
        if req.start.date() == now.date() and is_trading_day(now):
            if now.hour >= 9 and now.hour < 15:
                df = self.client.transaction(market='std', symbol=req.symbol, date=now.strftime("%Y%m%d"))
                return df
        
        df = self.client.transactions(market='std', symbol=req.symbol, date=req.start.strftime("%Y%m%d"))
        return df

    def finance(self, req: HistoryRequest, output: Callable = print):
        return self.client.finance(market='std', symbol=req.symbol)

    def get_bars(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
        output: Callable = print
    ) -> Optional[List[BarData]]:
        """
        获取历史K线数据（内部方法）
        :param symbol: 合约代码
        :param exchange: 交易所
        :param interval: K线周期
        :param start: 开始时间
        :param end: 结束时间
        :return: K线数据列表
        """
        # 从 TDX 离线数据读取 K 线数据
        try:
            frequency = 4 
            if interval == Interval.MINUTE:
                frequency = 7
            elif interval == Interval.HOUR:
                frequency = 3
            elif interval == Interval.DAILY:
                frequency = 4 
            elif interval == Interval.WEEKLY:
                frequency = 5 
            offset_ranges = self.split_date_range(start, end, interval)
            # output("offset_ranges",offset_ranges, start, end)
            all_bars = []
            for start_offset, end_offset in offset_ranges:

                # df = self.client.bars(
                #     symbol="000001",
                #     frequency=5,
                #     start=0,
                #     offset=800,
                #     adjust='qfq'
                # )
                df = self.client.bars(
                    symbol=symbol,
                    frequency=frequency,
                    start=start_offset,
                    offset=end_offset,
                    adjust='qfq'
                )
                # output("offset",end_offset, start_offset, df)
                if df is None or df.empty:
                    continue

                # 转换为BarData并合并
                bars = self._convert_df_to_bars(df, symbol, exchange, interval)
                all_bars = bars + all_bars

            return all_bars if all_bars else None
        except Exception as e:
            output(f"获取 K 线数据失败: {e}")
            return None