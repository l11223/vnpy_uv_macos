#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VNPY Mac 启动器 - 简化版
确保能稳定启动，可选模块加载失败不影响主程序
"""

import sys
import os
import traceback
from pathlib import Path


def show_error_dialog(title: str, message: str):
    """显示错误对话框"""
    try:
        import subprocess
        # 转义消息中的特殊字符
        safe_msg = message.replace('"', '\\"').replace("'", "\\'")[:300]
        script = f'display dialog "{safe_msg}" buttons {{"确定"}} default button "确定" with icon caution with title "{title}"'
        subprocess.run(['osascript', '-e', script], check=False)
    except:
        print(f"错误: {message}")


def main():
    """主入口函数"""
    log_file = None
    
    try:
        # 设置日志目录
        log_dir = Path.home() / ".vntrader" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "vnpy_startup.log"
        
        # 记录启动信息
        import datetime
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"启动时间: {datetime.datetime.now()}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Executable: {sys.executable}\n")
            f.write(f"{'='*60}\n")
        
        # 导入核心模块
        print("正在导入 VNPY 核心模块...")
        from vnpy.event import EventEngine
        from vnpy.trader.engine import MainEngine
        from vnpy.trader.ui import MainWindow, create_qapp
        print("✅ 核心模块导入成功")
        
        # 创建 Qt 应用
        print("正在创建 Qt 应用...")
        qapp = create_qapp()
        print("✅ Qt 应用创建成功")
        
        # 创建引擎
        print("正在创建交易引擎...")
        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        print("✅ 交易引擎创建成功")
        
        # 加载可选模块（失败不影响主程序）
        loaded_apps = []
        
        # CTA 策略模块
        try:
            from vnpy_ctastrategy import CtaStrategyApp
            main_engine.add_app(CtaStrategyApp)
            loaded_apps.append("CTA策略")
            print("✅ CTA策略模块已加载")
        except ImportError as e:
            print(f"⚠️ CTA策略模块未加载: {e}")
        except Exception as e:
            print(f"⚠️ CTA策略模块加载失败: {e}")
        
        # CTA 回测模块
        try:
            from vnpy_ctabacktester import CtaBacktesterApp
            main_engine.add_app(CtaBacktesterApp)
            loaded_apps.append("CTA回测")
            print("✅ CTA回测模块已加载")
        except ImportError as e:
            print(f"⚠️ CTA回测模块未加载: {e}")
        except Exception as e:
            print(f"⚠️ CTA回测模块加载失败: {e}")
        
        # 数据管理模块
        try:
            from vnpy_datamanager import DataManagerApp
            main_engine.add_app(DataManagerApp)
            loaded_apps.append("数据管理")
            print("✅ 数据管理模块已加载")
        except ImportError:
            print("ℹ️ 数据管理模块未安装")
        except Exception as e:
            print(f"⚠️ 数据管理模块加载失败: {e}")
        
        # 富途接口（可选）
        try:
            from vnpy_futu import FutuGateway
            main_engine.add_gateway(FutuGateway)
            loaded_apps.append("富途接口")
            print("✅ 富途接口已加载")
        except ImportError:
            print("ℹ️ 富途接口未安装")
        except Exception as e:
            print(f"⚠️ 富途接口加载失败: {e}")
        
        # 记录加载的模块
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"已加载模块: {', '.join(loaded_apps) if loaded_apps else '无'}\n")
        
        # 创建主窗口
        print("正在创建主窗口...")
        main_window = MainWindow(main_engine, event_engine)
        main_window.showMaximized()
        print("✅ 主窗口创建成功")
        
        # 记录成功
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write("✅ 启动成功\n")
        
        print("="*50)
        print("VNPY Mac 量化交易系统启动成功！")
        print(f"已加载模块: {', '.join(loaded_apps) if loaded_apps else '基础框架'}")
        print("="*50)
        
        return qapp.exec()
        
    except Exception as e:
        error_msg = str(e)
        
        # 记录错误
        if log_file:
            try:
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"❌ 启动失败: {error_msg}\n")
                    f.write(traceback.format_exc())
            except:
                pass
        
        # 显示错误
        show_error_dialog("VNPY 启动错误", error_msg)
        print(f"错误: {error_msg}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
