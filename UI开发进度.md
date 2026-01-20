# UI 开发进度

## ✅ 已完成

### 1. 历史数据管理器 UI
- ✅ 创建 `vnpy_history_manager` App 模块
- ✅ 实现 `HistoryManagerWidget` UI 窗口
- ✅ 在启动器中注册 App
- ✅ 自动显示在"功能"菜单中

**UI 功能：**
- 数据统计显示
- 缓存管理操作
- 刷新统计按钮
- 清空缓存按钮
- 美观的界面布局

## 🔄 待开发 UI

### 2. 状态监控器 UI
- [ ] 创建 `vnpy_status_monitor` App 模块
- [ ] 实现 `StatusMonitorWidget` UI 窗口
- [ ] 显示策略执行状态
- [ ] 实时监控面板

### 3. 多进程管理器 UI
- [ ] 创建 `vnpy_multiprocess` App 模块
- [ ] 实现 `MultiProcessWidget` UI 窗口
- [ ] 显示进程列表
- [ ] 进程管理操作

### 4. 优化指标计算 UI
- [ ] 创建 `vnpy_optimization` App 模块
- [ ] 实现 `OptimizationWidget` UI 窗口
- [ ] 指标计算界面
- [ ] 参数设置

### 5. 优化可视化 UI
- [ ] 创建 `vnpy_optimization_viz` App 模块
- [ ] 实现 `OptimizationVizWidget` UI 窗口
- [ ] 图表显示
- [ ] 结果可视化

### 6. 增强风控 UI
- [ ] 创建 `vnpy_risk_manager` App 模块
- [ ] 实现 `RiskManagerWidget` UI 窗口
- [ ] 风控规则配置
- [ ] 风险监控面板

## 📋 UI 开发规范

### App 模块结构
```
vnpy_xxx/
├── __init__.py          # 导出 App 类
├── app.py               # App 定义（继承 BaseApp）
├── engine.py            # 引擎类（继承 BaseEngine）
└── ui/
    ├── __init__.py      # 导出 Widget 类
    └── widget.py        # UI 窗口（继承 QWidget）
```

### App 类必需属性
- `app_name`: 唯一标识
- `app_module`: 模块路径
- `app_path`: 模块路径
- `display_name`: 菜单显示名称
- `engine_class`: 引擎类
- `widget_name`: Widget 类名
- `icon_name`: 图标文件名

### UI 设计原则
1. **美观布局**: 使用 QVBoxLayout, QHBoxLayout
2. **分组显示**: 使用 QGroupBox
3. **清晰标题**: 使用 QLabel 和样式
4. **操作按钮**: 使用 QPushButton
5. **Mac 风格**: 符合 macOS 设计规范

## 🎯 下一步

1. 等待测试历史数据管理器 UI
2. 根据反馈优化 UI
3. 继续开发其他功能的 UI
4. 确保每个功能都有对应的菜单入口
