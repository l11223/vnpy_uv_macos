#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNPY Mac 启动器 - 带错误捕获
适用于 PyInstaller 打包后的应用
"""

import sys
import os
import traceback
from pathlib import Path


def show_error_dialog(title: str, message: str):
    """显示错误对话框"""
    try:
        import subprocess
        script = f'display dialog "{message}" buttons {{"确定"}} default button "确定" with icon caution with title "{title}"'
        subprocess.run(['osascript', '-e', script], check=False)
    except:
        print(f"错误: {message}")


def main():
    """主入口函数"""
    try:
        # 设置日志目录
        log_dir = Path.home() / ".vntrader" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "vnpy_startup.log"
        
        # 记录启动信息
        with open(log_file, 'a', encoding='utf-8') as f:
            import datetime
            f.write(f"\n{'='*60}\n")
            f.write(f"启动时间: {datetime.datetime.now()}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Executable: {sys.executable}\n")
            f.write(f"{'='*60}\n")
        
        # 导入核心模块
        from vnpy.event import EventEngine
        from vnpy.trader.engine import MainEngine
        from vnpy.trader.ui import MainWindow, create_qapp
        
        # 创建 Qt 应用
        qapp = create_qapp()
        
        # 创建引擎
        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        
        # 配置通达信数据服务（A股历史数据）
        try:
            from vnpy.trader.setting import SETTINGS
            # 设置使用通达信数据服务
            SETTINGS["datafeed.name"] = "tdx"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write("✅ 通达信数据服务已配置\n")
        except Exception as e:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"⚠️ 通达信数据服务配置失败: {e}\n")
        
        # 加载可选模块
        try:
            from vnpy_ctastrategy import CtaStrategyApp
            main_engine.add_app(CtaStrategyApp)
        except ImportError:
            pass
        
        try:
            from vnpy_ctabacktester import CtaBacktesterApp
            main_engine.add_app(CtaBacktesterApp)
        except ImportError:
            pass
        
        try:
            from vnpy_futu.futu_gateway import FutuGateway
            main_engine.add_gateway(FutuGateway)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write("✅ FutuGateway 已加载\n")
        except ImportError as e:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"⚠️ FutuGateway 加载失败: {e}\n")
            # 不抛出异常，让程序继续运行
        
        # 创建主窗口
        main_window = MainWindow(main_engine, event_engine)
        main_window.showMaximized()
        
        # 注册增强功能 App（带 UI 窗口）
        try:
            from vnpy_history_manager import HistoryManagerApp
            main_engine.add_app(HistoryManagerApp)
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write("✅ 历史数据管理器 App 已注册\n")
        except Exception as e:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"⚠️ 历史数据管理器 App 注册失败: {e}\n")
        
        # 记录成功
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("✅ 启动成功\n")
        
        return qapp.exec()
        
    except Exception as e:
        error_msg = f"启动失败: {e}\n\n详细日志: ~/.vntrader/logs/vnpy_startup.log"
        
        # 记录错误
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"❌ 启动失败: {e}\n")
                f.write(traceback.format_exc())
        except:
            pass
        
        show_error_dialog("VNPY 启动错误", str(e)[:200])
        print(f"错误: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
