import sys
import os
from datetime import datetime
from time import sleep

# 将当前目录加入系统路径，确保能找到 vnpy_futu
sys.path.append(os.getcwd())

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.object import HistoryRequest
from vnpy.trader.database import get_database

# 尝试导入 FutuGateway
try:
    from vnpy_futu import FutuGateway
except ImportError:
    # 如果没安装，尝试从本地路径导入
    sys.path.append(os.path.join(os.getcwd(), "vnpy_futu"))
    from vnpy_futu import FutuGateway

def download_data():
    """下载数据脚本"""
    
    # 1. 配置参数
    SYMBOL = "00700"
    EXCHANGE = Exchange.SEHK
    START_DATE = datetime(2022, 1, 1)
    END_DATE = datetime.now()
    
    # Futu OpenD 配置 (请确认你的 OpenD 正在运行)
    FUTU_HOST = "127.0.0.1"
    FUTU_PORT = 11111
    FUTU_PWD = "123" # 这里的密码通常 OpenD 不需要，除非你设置了加密

    # 2. 初始化引擎
    print("正在初始化引擎...")
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(FutuGateway)

    # 3. 连接 Futu
    print(f"正在连接 Futu OpenD ({FUTU_HOST}:{FUTU_PORT})...")
    main_engine.connect({
        "地址": FUTU_HOST,
        "端口": FUTU_PORT,
        "密码": FUTU_PWD,
        "市场": "HK", # 港股
        "环境": 1     # 1: 真实环境 (0: 仿真) - 回测通常用真实历史数据
    })

    # 等待连接成功 (给一点时间让 Gateway 初始化)
    sleep(5)
    
    # 获取 Gateway 对象
    gateway = main_engine.get_gateway("FUTU")
    if not gateway:
        print("错误：无法获取 Futu Gateway，请检查连接。")
        return

    # 4. 构造数据请求
    req = HistoryRequest(
        symbol=SYMBOL,
        exchange=EXCHANGE,
        start=START_DATE,
        end=END_DATE,
        interval=Interval.MINUTE
    )

    print(f"开始下载 {SYMBOL}.{EXCHANGE.value} 数据...")
    print(f"时间范围: {START_DATE} - {END_DATE}")

    # 5. 调用接口下载
    # 注意：vnpy_futu 的 query_history 是同步的，会阻塞直到下载完成
    try:
        data = gateway.query_history(req)
    except Exception as e:
        print(f"下载过程中发生错误: {e}")
        main_engine.close()
        return

    if not data:
        print("未下载到任何数据。请检查：")
        print("1. 合约代码是否正确")
        print("2. 账户是否有该市场的行情权限")
        print("3. 时间范围内是否有交易")
        main_engine.close()
        return

    print(f"下载完成，共获取 {len(data)} 条K线数据。")

    # 6. 保存到数据库
    print("正在写入数据库...")
    database = get_database()
    database.save_bar_data(data)
    print("写入完成！")

    # 7. 退出
    main_engine.close()
    sys.exit(0)

if __name__ == "__main__":
    download_data()
