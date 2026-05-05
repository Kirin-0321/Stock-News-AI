"""
增强版每日新闻分析流程
爬取 → 清洗 → 合并去重 → 导出 → AI分析
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any
from .base import WorkflowBase


class EnhancedNewsFlow(WorkflowBase):
    """增强版每日新闻分析流程（含合并去重）"""
    
    workflow_id = "enhanced_news_flow"
    name = "增强版新闻分析流程"
    description = "自动执行爬取、清洗、合并去重、导出、AI分析的完整流程"
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务流
        
        Args:
            params: 执行参数
            
        Returns:
            执行结果
        """
        results = {}
        
        # Step 1: 爬取新闻
        self.log("Step 1: 开始爬取新闻...")
        crawler_file = self._run_crawler(params.get('crawler', {}))
        if not crawler_file:
            raise Exception("爬取新闻失败")
        results['crawler_file'] = crawler_file
        self.log(f"Step 1: ✓ 完成，文件: {crawler_file}")
        
        # Step 2: 清洗数据
        self.log("Step 2: 开始清洗数据...")
        cleaned_file = self._run_cleaner(crawler_file, params.get('cleaner', {}))
        if not cleaned_file:
            raise Exception("清洗数据失败")
        results['cleaned_file'] = cleaned_file
        self.log(f"Step 2: ✓ 完成，文件: {cleaned_file}")
        
        # Step 3: 合并去重（新增步骤）
        self.log("Step 3: 开始合并去重...")
        merge_result = self._run_merger(params.get('merger', {}))
        if not merge_result:
            raise Exception("合并去重失败")
        results['merge_result'] = merge_result
        self.log(f"Step 3: ✓ 完成，合并了 {merge_result.get('total_files', 0)} 个文件")
        self.log(f"  去重前: {merge_result.get('total_news_before', 0)} 条")
        self.log(f"  去重后: {merge_result.get('total_news_after', 0)} 条")
        self.log(f"  去除重复: {merge_result.get('duplicates_removed', 0)} 条")
        
        # Step 4: 导出数据
        self.log("Step 4: 开始导出数据...")
        export_file = self._run_export(params.get('export', {}))
        if not export_file:
            raise Exception("导出数据失败")
        results['export_file'] = export_file
        self.log(f"Step 4: ✓ 完成，文件: {export_file}")
        
        # Step 5: AI分析
        self.log("Step 5: 开始AI分析...")
        summary = self._get_summary(params.get('analyzer', {}))
        if summary:
            self.log(f"Step 5: 读取盘后总结成功，长度: {len(summary)}字")
        else:
            self.log("Step 5: 未找到盘后总结，将不使用盘后总结进行分析", level="warning")
        
        analysis_file = self._run_analyzer(export_file, summary, params.get('analyzer', {}))
        if not analysis_file:
            raise Exception("AI分析失败")
        results['analysis_file'] = analysis_file
        self.log(f"Step 5: ✓ 完成，文件: {analysis_file}")
        
        return results
    
    def _run_crawler(self, params: Dict[str, Any]) -> str:
        """
        执行爬虫任务
        
        Args:
            params: 爬虫参数
            
        Returns:
            生成的文件路径
        """
        try:
            from core.news_crawler_scroll import NewsCrawler
            
            scroll_times = params.get('scroll_times', 36)
            wait_seconds = params.get('wait_seconds', 6)
            auto_stop = params.get('auto_stop', True)
            
            self.log(f"  参数: 滚动{scroll_times}次, 等待{wait_seconds}秒, 自动停止={auto_stop}")
            
            crawler = NewsCrawler()
            
            # 如果启用自动停止，设置参数
            if auto_stop:
                from core.db_helper import get_latest_news_from_db, parse_news_time
                latest_news = get_latest_news_from_db()
                
                if latest_news:
                    latest_time = parse_news_time(latest_news)
                    latest_title = latest_news.get('title', '')
                    crawler.set_auto_stop(True, latest_time, latest_title)
                    self.log(f"  已启用自动停止，数据库最新新闻: {latest_title[:30]}...")
                else:
                    self.log(f"  未找到数据库新闻，将爬取全部")
            
            # 运行爬虫
            files = crawler.run(
                scroll_times=scroll_times,
                wait_seconds=wait_seconds
            )
            
            if files and len(files) > 0:
                # 返回最新生成的文件
                latest_file = files[-1]
                return latest_file
            else:
                return None
                
        except Exception as e:
            self.log(f"  爬虫执行失败: {str(e)}", level="error")
            raise
    
    def _run_cleaner(self, input_file: str, params: Dict[str, Any]) -> str:
        """
        执行数据清洗
        
        Args:
            input_file: 输入文件路径
            params: 清洗参数
            
        Returns:
            生成的清洗文件路径
        """
        try:
            from core.news_cleaner import NewsCleaner
            import json
            
            ai_provider = params.get('ai_provider', 'deepseek')
            batch_size = params.get('batch_size', 100)
            
            self.log(f"  参数: AI={ai_provider}, 批量={batch_size}")
            self.log(f"  输入: {input_file}")
            
            # 加载清洗标准
            criteria_file = 'config/cleaning_criteria.json'
            if os.path.exists(criteria_file):
                with open(criteria_file, 'r', encoding='utf-8') as f:
                    criteria_config = json.load(f)
                    criteria = criteria_config['default']['criteria']
                    self.log(f"  已加载清洗标准")
            else:
                self.log(f"  未找到清洗标准文件，使用默认标准", level="warning")
                criteria = "保留有投资价值的新闻"
            
            # 创建清洗器
            cleaner = NewsCleaner(criteria=criteria, ai_provider=ai_provider)
            
            # 使用 clean_news_files 方法
            result = cleaner.clean_news_files(
                file_paths=[input_file],
                batch_size=batch_size,
                auto_merge=True
            )
            
            kept = result['kept']
            removed = result['removed']
            
            self.log(f"  清洗完成: 保留{len(kept)}条, 移除{len(removed)}条")
            
            # 生成输出文件名
            base_name = os.path.basename(input_file)
            if base_name.endswith('_new.json'):
                output_name = base_name.replace('_new.json', '_clear.json')
            else:
                output_name = base_name.replace('.json', '_clear.json')
            
            output_path = os.path.join('data/cleaned', output_name)
            
            # 保存清洗结果
            os.makedirs('data/cleaned', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(kept, f, ensure_ascii=False, indent=2)
            
            return output_path
            
        except Exception as e:
            self.log(f"  清洗执行失败: {str(e)}", level="error")
            raise
    
    def _run_merger(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数据合并去重
        
        Args:
            params: 合并参数
            
        Returns:
            合并结果字典
        """
        try:
            from core.data_merger import DataMerger
            
            merge_mode = params.get('mode', 'recent')  # recent: 最近N个文件, all: 全部文件
            recent_count = params.get('recent_count', 5)  # 合并最近N个文件
            time_range_hours = params.get('time_range_hours', None)  # 时间范围（小时）
            
            self.log(f"  参数: 模式={merge_mode}, 最近文件数={recent_count}, 时间范围={time_range_hours}小时")
            
            # 获取可合并的文件列表
            all_files = DataMerger.get_mergeable_files('data/cleaned')
            
            if not all_files:
                self.log("  警告: 没有找到可合并的文件", level="warning")
                return None
            
            self.log(f"  找到 {len(all_files)} 个清洗文件")
            
            # 根据模式选择文件
            if merge_mode == 'recent':
                # 取最近的N个文件
                files_to_merge = all_files[-recent_count:] if len(all_files) > recent_count else all_files
            elif merge_mode == 'all':
                files_to_merge = all_files
            elif merge_mode == 'time_range' and time_range_hours:
                # 根据时间范围选择文件
                from datetime import datetime, timedelta
                cutoff_time = datetime.now() - timedelta(hours=time_range_hours)
                files_to_merge = []
                
                for file_path in all_files:
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time >= cutoff_time:
                        files_to_merge.append(file_path)
            else:
                files_to_merge = all_files
            
            self.log(f"  选择合并 {len(files_to_merge)} 个文件:")
            for f in files_to_merge:
                self.log(f"    - {os.path.basename(f)}")
            
            # 执行合并去重
            result = DataMerger.merge_and_split_by_date(
                file_paths=files_to_merge,
                output_dir='data/cleaned'
            )
            
            if result['success']:
                self.log(f"  合并成功，生成 {result['days_count']} 个按天分割的文件:")
                for daily_file in result['daily_files']:
                    self.log(f"    - {daily_file['filename']}: {daily_file['count']} 条")
                
                if result['deleted_files']:
                    self.log(f"  已删除 {len(result['deleted_files'])} 个旧文件")
            
            return result
            
        except Exception as e:
            self.log(f"  合并去重执行失败: {str(e)}", level="error")
            raise
    
    def _run_export(self, params: Dict[str, Any]) -> str:
        """
        执行数据导出
        
        Args:
            params: 导出参数
            
        Returns:
            导出的文件路径
        """
        try:
            source = params.get('source', 'cleaned')
            export_format = params.get('format', 'markdown')
            time_range_hours = params.get('time_range_hours', 24)
            
            self.log(f"  参数: 数据源={source}, 格式={export_format}, 时间范围={time_range_hours}小时")
            
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=time_range_hours)
            
            self.log(f"  时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
            
            # 使用统一的导出工具
            from core.news_exporter import NewsExporter
            exporter = NewsExporter()
            
            result = exporter.export(
                source=source,
                format=export_format,
                start_datetime=start_time,
                end_datetime=end_time
            )
            
            if not result['success']:
                raise Exception(result.get('error', '导出失败'))
            
            self.log(f"  导出成功: {result['news_count']} 条新闻")
            if result['time_range'][0] and result['time_range'][1]:
                self.log(f"  实际时间范围: {result['time_range'][0].strftime('%Y-%m-%d %H:%M')} ~ {result['time_range'][1].strftime('%Y-%m-%d %H:%M')}")
            
            return result['file_path']
            
        except Exception as e:
            self.log(f"  导出执行失败: {str(e)}", level="error")
            raise
    
    def _get_summary(self, params: Dict[str, Any]) -> str:
        """
        获取盘后总结
        
        Args:
            params: 分析参数
            
        Returns:
            盘后总结内容
        """
        summary_mode = params.get('summary_mode', 'auto')
        summary_file = params.get('summary_file', '')
        
        if summary_mode == 'auto':
            # 自动读取前日盘后总结
            return self._read_previous_day_summary_enhanced()
        elif summary_file:
            # 手动指定文件
            self.log(f"  读取指定盘后总结: {summary_file}")
            return self.read_file(summary_file)
        else:
            return ""
    
    def _read_previous_day_summary_enhanced(self) -> str:
        """读取前一天的盘后总结（增强版，支持实际路径）"""
        from datetime import datetime, timedelta
        import glob
        
        # 计算前一天日期
        yesterday = datetime.now() - timedelta(days=1)
        month = yesterday.month
        day = yesterday.day
        
        # 构建目录路径
        summary_dir = f"分析数据/盘后总结/{month}.{day}"
        
        if os.path.exists(summary_dir):
            # 查找目录下的md文件
            md_files = glob.glob(os.path.join(summary_dir, "*.md"))
            
            if md_files:
                # 选择第一个文件（或者可以选择最大的文件）
                summary_file = md_files[0]
                self.log(f"  读取盘后总结: {summary_file}")
                return self.read_file(summary_file)
            else:
                self.log(f"  目录 {summary_dir} 下没有找到md文件", level="warning")
        else:
            self.log(f"  未找到盘后总结目录: {summary_dir}", level="warning")
        
        return ""
    
    def _run_analyzer(self, input_file: str, summary: str, params: Dict[str, Any]) -> str:
        """
        执行AI分析
        
        Args:
            input_file: 输入文件路径
            summary: 盘后总结
            params: 分析参数
            
        Returns:
            分析结果文件路径
        """
        try:
            from core.ai_news_analyzer import AINewsAnalyzer
            
            template = params.get('template', 'short_term')
            
            self.log(f"  参数: 模板={template}")
            self.log(f"  输入: {input_file}")
            
            analyzer = AINewsAnalyzer()
            
            # 执行分析（auto_sectors 和 auto_stocks 已弃用）
            result = analyzer.analyze(
                file_path=input_file,
                template_id=template,
                market_summary=summary
            )
            
            if not result.get('success'):
                error = result.get('error', '未知错误')
                raise Exception(f"AI分析失败: {error}")
            
            # 返回报告文件路径
            report_file = result.get('report_file')
            news_count = result.get('news_count', 0)
            
            self.log(f"  分析完成，分析了 {news_count} 条新闻")
            self.log(f"  报告文件: {report_file}")
            
            return report_file
            
        except Exception as e:
            self.log(f"  分析执行失败: {str(e)}", level="error")
            raise

