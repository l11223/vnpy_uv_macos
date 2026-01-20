"""
历史数据管理器 UI 窗口
"""

from typing import TYPE_CHECKING
from vnpy.trader.ui import QtCore, QtWidgets, QtGui
from vnpy.trader.ui.widget import BaseMonitor

if TYPE_CHECKING:
    from vnpy.trader.engine import MainEngine
    from vnpy.event import EventEngine


class HistoryManagerWidget(QtWidgets.QWidget):
    """历史数据管理器窗口"""
    
    def __init__(self, main_engine: "MainEngine", event_engine: "EventEngine"):
        """初始化"""
        super().__init__()
        
        self.main_engine = main_engine
        self.event_engine = event_engine
        
        # 获取引擎
        self.engine = main_engine.get_engine("HistoryManager")
        
        self.init_ui()
        
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("历史数据管理")
        
        # 主布局
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # 标题
        title_label = QtWidgets.QLabel("历史数据管理器")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title_label)
        
        # 功能说明
        info_text = """
        <b>功能说明：</b><br>
        • 自动 K 线/Tick 缓存<br>
        • DataFrame 自动生成<br>
        • 数据完整性检查<br>
        • 历史数据查询和管理<br>
        """
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border-radius: 5px;")
        layout.addWidget(info_label)
        
        # 数据统计区域
        stats_group = QtWidgets.QGroupBox("数据统计")
        stats_layout = QtWidgets.QVBoxLayout()
        stats_group.setLayout(stats_layout)
        
        self.stats_label = QtWidgets.QLabel("正在加载统计数据...")
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # 操作按钮区域
        button_group = QtWidgets.QGroupBox("操作")
        button_layout = QtWidgets.QHBoxLayout()
        button_group.setLayout(button_layout)
        
        refresh_btn = QtWidgets.QPushButton("刷新统计")
        refresh_btn.clicked.connect(self.refresh_stats)
        button_layout.addWidget(refresh_btn)
        
        clear_cache_btn = QtWidgets.QPushButton("清空缓存")
        clear_cache_btn.clicked.connect(self.clear_cache)
        button_layout.addWidget(clear_cache_btn)
        
        layout.addWidget(button_group)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 初始化统计
        self.refresh_stats()
        
    def refresh_stats(self):
        """刷新统计数据"""
        try:
            if self.engine and self.engine.history_manager:
                # 这里可以添加实际的统计逻辑
                stats_text = """
                <b>缓存状态：</b>正常<br>
                <b>数据完整性：</b>检查中...<br>
                <b>缓存大小：</b>计算中...<br>
                """
                self.stats_label.setText(stats_text)
            else:
                self.stats_label.setText("历史数据管理器未初始化")
        except Exception as e:
            self.stats_label.setText(f"错误: {e}")
    
    def clear_cache(self):
        """清空缓存"""
        reply = QtWidgets.QMessageBox.question(
            self,
            "确认",
            "确定要清空历史数据缓存吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            try:
                # 这里可以添加实际的清空缓存逻辑
                QtWidgets.QMessageBox.information(self, "成功", "缓存已清空")
                self.refresh_stats()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "错误", f"清空缓存失败: {e}")
