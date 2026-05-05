"""
新闻分析页面
分析新闻影响力
"""

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QComboBox, QSpinBox, QTextBrowser,
                             QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor

from gui.utils.styles import *
from gui.workers.analysis_worker import AnalysisWorker
import os
from datetime import datetime


class AnalysisPage(QWidget):
    """新闻分析页面"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题
        title = QLabel("📊 新闻分析")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #262626;")
        layout.addWidget(title)
        
        # 参数设置
        params_group = self.create_params_group()
        layout.addWidget(params_group)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.analyze_btn = QPushButton("▶ 开始分析")
        self.analyze_btn.setStyleSheet(BUTTON_PRIMARY)
        self.analyze_btn.setMinimumHeight(40)
        self.analyze_btn.clicked.connect(self.start_analysis)
        control_layout.addWidget(self.analyze_btn)
        
        control_layout.addStretch()
        
        layout.addLayout(control_layout)
        
        # 日志显示
        log_group = self.create_log_group()
        layout.addWidget(log_group, 1)
        
        # 结果显示
        result_group = self.create_result_group()
        layout.addWidget(result_group)
        
    def create_params_group(self):
        """创建参数设置组"""
        group = QGroupBox("分析参数")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 20, 15, 15)
        
        # 选择文件
        layout.addWidget(QLabel("数据文件:"))
        self.file_combo = QComboBox()
        self.file_combo.setStyleSheet(COMBOBOX_STYLE)
        self.file_combo.setMinimumWidth(300)
        layout.addWidget(self.file_combo)
        
        # 刷新文件列表按钮
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("刷新文件列表")
        refresh_btn.clicked.connect(self.load_json_files)
        layout.addWidget(refresh_btn)
        
        layout.addSpacing(20)
        
        # 最小影响分数
        layout.addWidget(QLabel("最小影响分数:"))
        self.min_score_spin = QSpinBox()
        self.min_score_spin.setRange(1, 10)
        self.min_score_spin.setValue(8)
        self.min_score_spin.setToolTip("只分析影响分数高于此值的新闻")
        self.min_score_spin.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.min_score_spin)
        
        layout.addStretch()
        
        group.setLayout(layout)
        
        # 初始加载文件列表
        self.load_json_files()
        
        return group
    
    def create_log_group(self):
        """创建日志显示组"""
        group = QGroupBox("分析日志")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 20, 15, 15)
        
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet(TEXTBROWSER_STYLE + """
            QTextBrowser {
                font-family: Consolas, monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_browser)
        
        group.setLayout(layout)
        return group
    
    def create_result_group(self):
        """创建结果显示组"""
        group = QGroupBox("分析结果")
        group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #d9d9d9;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(15, 20, 15, 15)
        
        self.result_label = QLabel("等待分析...")
        self.result_label.setStyleSheet("color: #8c8c8c; font-size: 13px;")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        
        layout.addStretch()
        
        self.open_report_btn = QPushButton("📄 打开报告")
        self.open_report_btn.setStyleSheet(BUTTON_SUCCESS)
        self.open_report_btn.setEnabled(False)
        self.open_report_btn.clicked.connect(self.open_report)
        layout.addWidget(self.open_report_btn)
        
        group.setLayout(layout)
        return group
    
    def load_json_files(self):
        """加载JSON文件列表（包括原始数据和导出数据）"""
        self.file_combo.clear()
        
        file_list = []
        
        # 1. 加载导出目录中的文件
        exports_dir = 'data/exports'
        if os.path.exists(exports_dir):
            for export_folder in os.listdir(exports_dir):
                folder_path = os.path.join(exports_dir, export_folder)
                if os.path.isdir(folder_path):
                    for filename in os.listdir(folder_path):
                        if filename.endswith('.json'):
                            # 使用相对路径，格式：exports/目录名/文件名
                            rel_path = os.path.join('exports', export_folder, filename)
                            # 添加标签区分
                            display_name = f"[导出] {export_folder}/{filename}"
                            file_list.append((display_name, rel_path))
        
        # 2. 加载原始数据目录中的文件
        raw_dir = 'data/raw'
        if os.path.exists(raw_dir):
            for filename in os.listdir(raw_dir):
                if filename.endswith('.json'):
                    rel_path = os.path.join('raw', filename)
                    display_name = f"[原始] {filename}"
                    file_list.append((display_name, rel_path))
        
        # 按显示名称排序（最新的在前面）
        file_list.sort(key=lambda x: x[0], reverse=True)
        
        # 添加到下拉框（存储实际路径为数据）
        for display_name, rel_path in file_list:
            self.file_combo.addItem(display_name, rel_path)
    
    def start_analysis(self):
        """开始分析"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "警告", "分析正在进行中！")
            return
        
        if self.file_combo.count() == 0:
            QMessageBox.warning(self, "警告", "没有可分析的文件！")
            return
        
        # 禁用分析按钮
        self.analyze_btn.setEnabled(False)
        self.open_report_btn.setEnabled(False)
        
        # 清空日志和结果
        self.log_browser.clear()
        self.result_label.setText("分析中...")
        
        # 添加日志
        self.add_log("=" * 60)
        self.add_log(f"开始分析 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.add_log("=" * 60)
        
        # 创建工作线程
        # 获取实际的文件路径（从userData）
        json_file = self.file_combo.currentData()
        if not json_file:
            # 如果没有userData，使用文本（兼容旧数据）
            json_file = self.file_combo.currentText()
        min_score = self.min_score_spin.value()
        
        self.worker = AnalysisWorker(json_file, min_score)
        
        # 连接信号
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.log_message.connect(self.add_log)
        
        # 启动线程
        self.worker.start()
    
    def on_analysis_finished(self, result):
        """分析完成"""
        self.add_log("=" * 60)
        self.add_log("分析完成！")
        self.add_log("=" * 60)
        
        # 显示结果
        result_text = f"""
重要新闻总数: {result.get('total_news', 0)}
🔴 重大影响 (≥10分): {result.get('critical_impact', 0)}
🟠 高度影响 (7-9分): {result.get('high_impact', 0)}
🟡 中等影响 (5-6分): {result.get('medium_impact', 0)}
        """.strip()
        
        self.result_label.setText(result_text)
        self.result_label.setStyleSheet("color: #262626; font-size: 14px; font-weight: bold;")
        
        # 保存报告路径
        self.last_report = result.get('report_file', '')
        
        # 启用按钮
        self.analyze_btn.setEnabled(True)
        if self.last_report and os.path.exists(self.last_report):
            self.open_report_btn.setEnabled(True)
        
        QMessageBox.information(self, "成功", "分析完成！")
    
    def on_analysis_error(self, error_msg):
        """分析出错"""
        self.add_log(f"错误: {error_msg}")
        self.result_label.setText(f"分析失败: {error_msg}")
        self.result_label.setStyleSheet("color: #ff4d4f; font-size: 13px;")
        self.analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", error_msg)
    
    def open_report(self):
        """打开报告（使用Typora）"""
        if hasattr(self, 'last_report') and self.last_report:
            import subprocess
            import sys
            
            # 智能获取Typora路径（兼容打包后的exe）
            if getattr(sys, 'frozen', False):
                # 打包后的程序
                exe_dir = os.path.dirname(sys.executable)
                typora_path = os.path.join(exe_dir, 'Typora', 'Typora.exe')
            else:
                # 开发环境
                typora_path = os.path.join(os.getcwd(), 'Typora', 'Typora.exe')
            
            # 如果Typora存在，使用Typora打开
            if os.path.exists(typora_path):
                try:
                    subprocess.Popen([typora_path, os.path.abspath(self.last_report)])
                    self.add_log(f"已使用Typora打开报告: {os.path.basename(self.last_report)}")
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"使用Typora打开失败: {str(e)}")
            else:
                # Typora不存在，使用系统默认程序
                try:
                    os.startfile(self.last_report)
                    self.add_log(f"已打开报告: {os.path.basename(self.last_report)}")
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"打开报告失败: {str(e)}")
    
    def add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_browser.append(f"[{timestamp}] {message}")
        self.log_browser.moveCursor(QTextCursor.End)
    
    def refresh(self):
        """刷新页面（当切换到此页面时调用）"""
        self.load_json_files()

