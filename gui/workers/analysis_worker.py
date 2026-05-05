"""
分析后台工作线程
"""

from PyQt5.QtCore import QThread, pyqtSignal
import traceback


class AnalysisWorker(QThread):
    """分析工作线程"""

    # 信号定义
    finished = pyqtSignal(dict)  # result
    error = pyqtSignal(str)  # error_message
    log_message = pyqtSignal(str)  # log message

    def __init__(self, json_file, min_score=8):
        super().__init__()
        self.json_file = json_file
        self.min_score = min_score

    def run(self):
        """运行分析"""
        try:
            self.log_message.emit(f"开始分析: {self.json_file}")
            self.log_message.emit(f"最小影响分数: {self.min_score}")

            # 导入分析模块
            from core.analyze_news_impact import NewsImpactAnalyzer
            import os

            # 构建完整路径
            if not os.path.isabs(self.json_file):
                # 如果是相对路径，检查是否已包含data前缀
                if (self.json_file.startswith('raw\\') or
                        self.json_file.startswith('exports\\')):
                    json_path = os.path.join('data', self.json_file)
                elif (self.json_file.startswith('raw/') or
                        self.json_file.startswith('exports/')):
                    json_path = os.path.join('data', self.json_file)
                else:
                    # 兼容旧格式（直接是文件名）
                    json_path = os.path.join('data', 'raw', self.json_file)
            else:
                json_path = self.json_file

            self.log_message.emit(f"文件路径: {json_path}")

            # 检查文件是否存在
            if not os.path.exists(json_path):
                raise FileNotFoundError(f"文件不存在: {json_path}")

            # 创建分析器
            analyzer = NewsImpactAnalyzer()

            self.log_message.emit("正在分析新闻...")

            # 执行分析（传递文件路径和最小分数）
            important_news = analyzer.analyze_file(
                json_path, self.min_score)

            # 统计结果
            if important_news:
                critical = [n for n in important_news if n['score'] >= 10]
                high = [n for n in important_news
                        if 7 <= n['score'] < 10]
                medium = [n for n in important_news
                          if 5 <= n['score'] < 7]

                self.log_message.emit("分析完成！")
                self.log_message.emit(f"重要新闻总数: {len(important_news)}")
                self.log_message.emit(
                    f"重大影响 (≥10分): {len(critical)}")
                self.log_message.emit(
                    f"高度影响 (7-9分): {len(high)}")
                self.log_message.emit(
                    f"中等影响 (5-6分): {len(medium)}")

                # 构建结果字典
                basename = os.path.basename(json_path).replace('.json', '')
                result = {
                    'total_news': len(important_news),
                    'critical_impact': len(critical),
                    'high_impact': len(high),
                    'medium_impact': len(medium),
                    'news_list': important_news,
                    'report_file': f"data/analysis/{basename}_重点分析.md"
                }
            else:
                self.log_message.emit("分析完成！未发现重要新闻。")
                result = {
                    'total_news': 0,
                    'critical_impact': 0,
                    'high_impact': 0,
                    'medium_impact': 0,
                    'news_list': [],
                    'report_file': None
                }

            self.finished.emit(result)

        except Exception as e:
            error_msg = f"分析失败: {str(e)}"
            self.log_message.emit(error_msg)
            self.error.emit(error_msg)
            print(traceback.format_exc())
