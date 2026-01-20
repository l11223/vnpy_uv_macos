from datetime import datetime
from vnpy_ctastrategy.backtesting import BacktestingEngine
from vnpy.trader.constant import Interval

# 导入海龟策略
from strategies.turtle_strategy import TurtleStrategy

def run():
    # 1. 创建回测引擎
    engine = BacktestingEngine()
    
    # 2. 设置回测参数
    engine.set_parameters(
        vt_symbol="00700.SEHK",     # 腾讯控股 (港股)
        interval="1m",              # 1分钟线
        start=datetime(2022, 1, 1), # 改一下日期到最近
        end=datetime(2024, 6, 1),
        rate=0.0015,                # 港股手续费/印花税约千分之1.5
        slippage=0.1,               # 滑点 0.1
        size=1,                     # 股票通常设为1
        pricetick=0.2,              # 腾讯最小价格跳动通常为0.2
        capital=1_000_000,
    )

    # 3. 添加策略
    engine.add_strategy(TurtleStrategy, {})

    # 4. 加载数据
    print("开始加载历史数据...")
    engine.load_data()

    # 5. 运行回测
    print("开始回测...")
    engine.run_backtesting()

    # 6. 计算盈亏结果
    print("计算结果...")
    df = engine.calculate_result()
    
    # 7. 打印统计指标
    print("----------------------------------------")
    engine.calculate_statistics()

if __name__ == "__main__":
    run()
