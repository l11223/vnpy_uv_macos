#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试当前集成的功能模块
"""

import sys
import traceback

def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试模块导入")
    print("=" * 60)
    
    modules = [
        ("vnpy.trader.platform_utils", "平台工具"),
        ("vnpy.trader.multiprocess_manager", "多进程管理器"),
        ("vnpy.trader.enhanced_cta_template", "增强策略模板"),
        ("vnpy.trader.history_manager", "历史数据管理"),
        ("vnpy.trader.data_filter", "数据过滤"),
        ("vnpy.trader.multiprocess_backtester", "多进程回测"),
        ("vnpy.trader.optimization_metrics", "优化指标"),
        ("vnpy.trader.optimization_visualization", "优化可视化"),
        ("vnpy.trader.enhanced_risk_manager", "增强风控"),
        ("vnpy.trader.status_monitor", "状态监控"),
        ("vnpy_tdx.tdx_datafeed", "通达信数据接口"),
        ("vnpy_futu.futu_gateway", "富途接口"),
    ]
    
    results = []
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"✅ {display_name} ({module_name})")
            results.append((display_name, True, None))
        except Exception as e:
            print(f"❌ {display_name} ({module_name}): {e}")
            results.append((display_name, False, str(e)))
    
    return results

def test_ui_structure():
    """测试 UI 结构"""
    print("\n" + "=" * 60)
    print("测试 UI 结构")
    print("=" * 60)
    
    try:
        from vnpy.trader.ui.mainwindow import MainWindow
        from vnpy.trader.engine import MainEngine
        from vnpy.event import EventEngine
        
        print("✅ MainWindow 导入成功")
        print("✅ MainEngine 导入成功")
        print("✅ EventEngine 导入成功")
        
        # 检查是否有 UI 方法
        if hasattr(MainWindow, 'init_menu'):
            print("✅ MainWindow 有 init_menu 方法")
        else:
            print("❌ MainWindow 缺少 init_menu 方法")
        
        return True
    except Exception as e:
        print(f"❌ UI 结构测试失败: {e}")
        traceback.print_exc()
        return False

def test_app_registration():
    """测试 App 注册"""
    print("\n" + "=" * 60)
    print("测试 App 注册")
    print("=" * 60)
    
    try:
        from vnpy.event import EventEngine
        from vnpy.trader.engine import MainEngine
        
        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        
        # 检查已注册的 App
        apps = main_engine.get_all_apps()
        print(f"已注册的 App 数量: {len(apps)}")
        for app in apps:
            print(f"  - {app.display_name} ({app.app_name})")
        
        # 检查已注册的 Gateway
        gateways = main_engine.get_all_gateway_names()
        print(f"\n已注册的 Gateway 数量: {len(gateways)}")
        for gateway in gateways:
            print(f"  - {gateway}")
        
        return True
    except Exception as e:
        print(f"❌ App 注册测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("VNPY Mac 量化系统 - 功能测试")
    print("=" * 60)
    
    # 测试导入
    import_results = test_imports()
    
    # 测试 UI 结构
    ui_ok = test_ui_structure()
    
    # 测试 App 注册
    app_ok = test_app_registration()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    failed_imports = [r for r in import_results if not r[1]]
    if failed_imports:
        print(f"\n❌ 导入失败的模块 ({len(failed_imports)}):")
        for name, _, error in failed_imports:
            print(f"  - {name}: {error}")
    else:
        print("\n✅ 所有模块导入成功")
    
    if ui_ok:
        print("✅ UI 结构正常")
    else:
        print("❌ UI 结构有问题")
    
    if app_ok:
        print("✅ App 注册正常")
    else:
        print("❌ App 注册有问题")
    
    print("\n" + "=" * 60)
    print("下一步：为缺少 UI 的功能创建窗口")
    print("=" * 60)
    
    missing_ui_features = [
        "历史数据管理器",
        "状态监控器",
        "多进程管理器",
        "优化指标计算",
        "优化可视化",
        "增强风控",
    ]
    
    print("\n需要创建 UI 的功能：")
    for i, feature in enumerate(missing_ui_features, 1):
        print(f"  {i}. {feature}")

if __name__ == "__main__":
    main()
