"""
A股新闻影响分析助手
自动识别和分类对A股有重大影响的新闻
"""

import json
import os
import re
from datetime import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, TypedDict


class KeywordConfig(TypedDict):
    keywords: List[str]
    weight: int
    category: str


class NewsImpactAnalyzer:
    """新闻影响分析器"""

    def __init__(self, mode: str = "short", *args, **kwargs):
        """
        mode:
          - "short": 面向A股短线/事件驱动（默认）
          - "default": 保留原有更偏“宏观分类统计”的风格（兼容）

        兼容性说明：
        早期版本曾有人误传入 (json_path, min_score) 导致崩溃；
        这里保留 *args 以避免 GUI/脚本侧误用直接报错。
        """
        self.mode = (mode or "short").lower()

        # 定义关键词权重
        self.keywords_config: Dict[str, KeywordConfig] = {
            # 最高优先级 - 货币/财政政策 (权重: 10)
            '货币政策': {
                'keywords': [
                    '央行', '降准', '降息', 'MLF', 'LPR',
                    '逆回购', '公开市场', '基准利率', '存款准备金',
                ],
                'weight': 10,
                'category': '货币政策'
            },
            # 最高优先级 - 监管政策 (权重: 10)
            '监管政策': {
                'keywords': [
                    '证监会', 'IPO', '再融资', '减持',
                    '退市', '注册制', '印花税', '交易制度',
                ],
                'weight': 10,
                'category': '监管政策'
            },
            # 最高优先级 - 宏观数据 (权重: 9)
            '宏观经济': {
                'keywords': [
                    'GDP', 'PMI', 'CPI', 'PPI', '社融',
                    'M1', 'M2', '进出口', '统计局', '财政收入',
                ],
                'weight': 9,
                'category': '宏观经济'
            },
            # 高优先级 - 产业政策 (权重: 8)
            '产业政策': {
                'keywords': [
                    '工信部', '发改委', '产业政策', '补贴',
                    '专项债', '新基建', '碳中和', '双碳',
                ],
                'weight': 8,
                'category': '产业政策'
            },
            # 高优先级 - 房地产 (权重: 8)
            '房地产': {
                'keywords': [
                    '房地产', '商品房', '房价', '地产调控',
                    '限购', '房贷利率', '保障房', '棚改',
                ],
                'weight': 8,
                'category': '房地产'
            },
            # 最高优先级 - 美国 (权重: 10)
            '美国影响': {
                'keywords': [
                    '美联储', '美国经济', '美国GDP', '美元指数',
                    '美国加息', '美国降息', '特朗普', '拜登',
                    '美国通胀', '美国CPI', '美国失业率', '美股',
                    '标普500', '纳斯达克', '道琼斯', '美债', '美国财政',
                ],
                'weight': 8,
                'category': '美国影响'
            },
            # 高优先级 - 欧盟 (权重: 7)
            '欧盟影响': {
                'keywords': [
                    '欧洲央行', '欧元区', '欧盟经济', '欧洲',
                    '德国经济', '法国经济', '意大利经济',
                    '西班牙', '欧元', '欧债', 'ECB',
                ],
                'weight': 5,
                'category': '欧盟影响'
            },
            # 中优先级 - 日本 (权重: 5)
            '日本影响': {
                'keywords': [
                    '日本央行', '日本经济', '日本GDP',
                    '日元', '日经指数', '日本通胀', '东京',
                ],
                'weight': 3,
                'category': '日本影响'
            },
            # 极低优先级 - 其他国家 (权重: 1)
            '其他国家': {
                'keywords': [
                    '哥伦比亚', '秘鲁', '智利', '阿根廷', '巴西',
                    '土耳其', '南非', '印尼', '印度尼西亚', '泰国',
                    '越南', '菲律宾', '马来西亚', '埃及', '尼日利亚',
                    '肯尼亚', '塞拉利昂', '津巴布韦', '加纳',
                    '巴基斯坦', '孟加拉', '斯里兰卡', '乌克兰', '波兰',
                    '捷克', '匈牙利', '罗马尼亚', '保加利亚', '新西兰',
                    '澳洲', '澳大利亚', '加拿大', '瑞士', '瑞典',
                    '挪威', '丹麦', '荷兰', '比利时', '奥地利', '爱尔兰',
                    '葡萄牙', '希腊', '芬兰', '韩国', '新加坡', '墨西哥',
                    '印度', '俄罗斯', '沙特', '阿联酋', '卡塔尔',
                ],
                'weight': 1,
                'category': '其他国家'
            },
            # 中国相关 (权重: 8) - 与美国持平重要
            '中国贸易': {
                'keywords': ['人民币汇率', '关税', '贸易战', '中美', '中欧', '中日'],
                'weight': 8,
                'category': '国际贸易'
            },
            # 中高优先级 - 科技板块 (权重: 7)
            '科技': {
                'keywords': [
                    '芯片', '半导体', '人工智能', 'AI',
                    '5G', '6G', '新能源车', '光伏', '储能', '锂电池',
                ],
                'weight': 7,
                'category': '科技板块'
            },
            # 短线常炒 - 智能驾驶/智能网联 (权重: 7)
            '智能驾驶': {
                'keywords': [
                    '自动驾驶', '智能驾驶', '高阶智驾', '城市NOA', 'NOA',
                    'Robotaxi', '车路协同', '智能网联', 'L3', 'L4',
                    '道路测试', '准入许可', '专用号牌', '域控', '激光雷达',
                ],
                'weight': 7,
                'category': '智能驾驶'
            },
            # 短线常炒 - 低空经济 (权重: 7)
            '低空经济': {
                'keywords': [
                    '低空经济', '通用航空', '通航', '无人机', 'eVTOL',
                    '电动垂直起降', '飞行汽车', '城市空中交通', 'UAM',
                    '空域', '适航', '试飞', '起降点', '低空航线',
                ],
                'weight': 7,
                'category': '低空经济'
            },
            # 短线热点 - 核聚变/核电/核裂变 (权重: 7)
            '核电核聚变': {
                'keywords': [
                    '可控核聚变', '核聚变', '聚变堆', '托卡马克', 'EAST',
                    '人造太阳', 'ITER', '核裂变', '核电', '核岛',
                    '小堆', 'SMR', '核燃料', '铀', '乏燃料',
                    '核安全', '核电站',
                ],
                'weight': 7,
                'category': '核电核聚变'
            },
            # 短线热点 - 医疗健康/医药 (权重: 6)
            '医疗健康': {
                'keywords': [
                    '医疗', '医药', '创新药', '医保', '集采',
                    '医疗器械', 'IVD', '诊断', '药品', '疫苗',
                    '手术机器人', 'AI医疗', 'CRO', 'CDMO',
                    '生物医药', '医疗服务', '医院',
                ],
                'weight': 6,
                'category': '医疗健康'
            },
            # 风险/主题 - 台海/两岸 (权重: 6)
            '台海两岸': {
                'keywords': [
                    '海峡两岸', '两岸', '台海', '台湾',
                    '统一', '反分裂', '两岸关系', '台独',
                ],
                'weight': 6,
                'category': '台海两岸'
            },
            # 短线热点 - 军工 (权重: 7)
            '军工': {
                'keywords': [
                    '军工', '国防', '军贸', '装备', '导弹',
                    '雷达', '舰艇', '战机', '无人作战', '演训',
                    '军演', '武器', '防务',
                ],
                'weight': 7,
                'category': '军工'
            },
            # 中优先级 - 消费 (权重: 6)
            '消费': {
                'keywords': ['消费', '零售', '白酒', '茅台', '医药', '创新药', '免税', '旅游'],
                'weight': 6,
                'category': '消费板块'
            },
            # 中优先级 - 金融 (权重: 6)
            '金融': {
                'keywords': ['银行', '保险', '券商', '信托', '不良率', '息差', '理财'],
                'weight': 6,
                'category': '金融板块'
            },
            # 中优先级 - 周期 (权重: 5)
            '周期': {
                'keywords': ['有色', '钢铁', '煤炭', '化工', '水泥', '建材', '工程机械'],
                'weight': 5,
                'category': '周期板块'
            },
            # 中优先级 - 资金流向 (权重: 7)
            '资金面': {
                'keywords': [
                    '北上资金', '外资', 'QFII', 'ETF',
                    '融资融券', '大宗交易', '减持',
                ],
                'weight': 7,
                'category': '资金流向'
            },
        }

        # ===== 短线增强：题材/事件触发词（用于 mode=short）=====
        # 题材标签（不改变原有 categories 的兼容输出；额外输出 themes / tags）
        self.short_themes: Dict[str, List[str]] = {
            "半导体/先进制程": [
                # 注意：避免用“芯片”这类过宽词导致智驾/手机等新闻误入
                r"2nm", r"3nm", r"5nm", r"先进制程", r"半导体",
                r"晶圆", r"12英寸", r"光刻", r"EUV", r"EDA",
                r"光计算", r"光子", r"存储器", r"DRAM", r"NAND",
            ],
            "AI算力/大模型": [
                r"大模型", r"训练", r"推理", r"智算",
                r"算力", r"算力本", r"TOPS", r"CUDA", r"生成式",
                r"GPU", r"智算中心", r"服务器", r"数据中心",
            ],
            "智能驾驶/智能网联": [
                r"\bL3\b", r"\bL4\b", r"自动驾驶", r"智能驾驶",
                r"高阶智驾", r"城市NOA", r"\bNOA\b", r"\bFSD\b",
                r"Robotaxi", r"车路协同", r"智能网联", r"车载摄像头",
                r"激光雷达", r"毫米波雷达", r"域控制器", r"域控",
                r"高精地图", r"道路测试", r"准入许可", r"专用号牌",
            ],
            "低空经济": [
                r"低空经济", r"通用航空", r"\bUAM\b", r"\beVTOL\b",
                r"电动垂直起降", r"飞行汽车", r"城市空中交通",
                r"空域", r"适航", r"试飞", r"起降点", r"低空航线",
                r"无人机", r"通航机场", r"低空大通道",
            ],
            "核聚变/核电": [
                r"可控核聚变", r"核聚变", r"聚变堆", r"托卡马克",
                r"\bEAST\b", r"人造太阳", r"\bITER\b", r"聚变装置",
                r"核裂变", r"核电", r"核电站", r"核岛", r"小堆", r"\bSMR\b",
                r"核燃料", r"乏燃料", r"铀矿", r"核安全",
            ],
            "医疗健康/医药": [
                r"医疗", r"医药", r"创新药", r"医保", r"集采",
                r"医疗器械", r"\bIVD\b", r"诊断", r"药品", r"疫苗",
                r"手术机器人", r"AI医疗", r"\bCRO\b", r"\bCDMO\b",
                r"生物医药", r"医疗服务",
            ],
            "台海/两岸": [
                r"海峡两岸", r"两岸", r"台海", r"台湾",
                r"统一", r"反分裂", r"两岸关系", r"台独",
            ],
            "军工/国防": [
                r"军工", r"国防", r"军贸", r"防务",
                r"导弹", r"雷达", r"卫星侦察", r"反导",
                r"舰艇", r"战机", r"军演", r"演训",
            ],
            "黄金/有色": [
                r"黄金", r"金价", r"白银", r"铜价", r"铝价",
                r"稀土", r"钴", r"镍", r"锂矿",
            ],
            "传媒游戏": [
                r"传媒", r"短剧", r"游戏", r"影视", r"动画",
                r"IP", r"票房", r"文娱",
            ],
            "AI应用/软件": [
                r"AI应用", r"智能体", r"Agent", r"Copilot",
                r"企业AI", r"RPA", r"ERP", r"SaaS", r"软件",
                r"国产软件", r"信创",
            ],
            "机器人/具身智能": [
                r"人形", r"机器人", r"具身智能", r"灵巧手",
                r"减速器", r"伺服", r"VLA", r"开源",
            ],
            "商业航天/卫星互联网": [
                r"商业航天", r"卫星", r"低轨", r"星座", r"火箭",
                r"发射", r"卫星通信", r"测控", r"FPGA",
            ],
            "消费政策/免税文旅": [
                r"离境退税", r"免税", r"封关", r"自贸港",
                r"文旅", r"入境游", r"机场旅客吞吐量",
            ],
            "能源/油气与电力": [
                r"油田", r"油气", r"致密油", r"页岩油", r"储气库",
                r"电网", r"供电", r"风电", r"光伏",
            ],
            "储能/电池": [
                r"储能", r"锂电池", r"固态电池", r"液流电池",
                r"电池健康度", r"电解液", r"正极", r"负极",
            ],
            "水利/基建": [
                r"南水北调", r"水务", r"水利",
                r"专项债", r"基建", r"高铁", r"轨交",
            ],
        }

        # 事件驱动强触发词：更像短线“催化剂”
        self.short_event_triggers: List[Tuple[str, str, int]] = [
            ("首发/首个", r"首(块|个|次|家)", 4),
            ("获批/牌照", r"(获批|获准|批准|许可|准入|牌照|专用号牌)", 5),
            (
                "发布/启动",
                r"(发布|推出|上线|开源|揭牌|启动|落地|通车|开工|点火起飞|成功发射|试飞|适航)",
                4,
            ),
            ("中标/订单", r"(中标|订单|签约|签署|合作|战略合作|定点)", 4),
            ("量产/扩产", r"(量产|扩产|投产|产能|募资|IPO受理|辅导)", 3),
            ("业绩上修", r"(上修|预增|大幅增长|创历史新高|突破)", 3),
            ("利空事件", r"(终止|撤回|下调|暂停|处罚|立案|被查|退市)", -4),
        ]

        # 数字强度（金额/规模/倍数/性能）加分：短线常看“量化冲击”
        self.short_number_patterns: List[Tuple[re.Pattern[str], int]] = [
            (
                re.compile(
                    r"(\d+(\.\d+)?)(万亿|亿|亿元|万|万吨|万卡|十万卡|TOPS|倍|%|GWh)"
                ),
                1,
            ),
        ]

        # 明显与A股短线无关的噪声词：除非同时命中强题材/政策，否则降权
        self.noise_patterns: List[re.Pattern[str]] = [
            re.compile(
                r"(枪击|扫毒|拘捕|毒品|涉黄|地震|火山|洪水|空难|坠机|恐袭|爆炸|抗议者要求辞职|投石|官司八卦)"
            ),
        ]

        # 更细的否定词（用于情绪判断）
        self.negations = [
            "不", "未", "无", "难", "未能",
            "暂停", "终止", "下调", "撤回",
        ]

        # 利空关键词
        self.negative_keywords = [
            '下跌', '下滑', '减少', '降低', '疲软', '放缓', '收紧',
            '限制', '违规', '处罚', '造假', '亏损', '爆雷', '退市',
            '加息', '缩表', '制裁', '冲突', '战争'
        ]

        # 利好关键词
        self.positive_keywords = [
            '上涨', '增长', '回升', '改善', '复苏', '强劲', '放松',
            '支持', '补贴', '减税', '降准', '降息', '盈利', '增厚',
            '突破', '创新', '订单', '扩产'
        ]

    def _safe_get_datetime_str(self, news: Dict[str, Any]) -> str:
        """尽量从不同字段拿到 datetime 字符串（兼容 raw/export 两种格式）"""
        return (
            news.get("datetime")
            or news.get("time")
            or news.get("date_time")
            or ""
        )

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """解析常见时间格式，失败返回 None"""
        if not dt_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(dt_str.strip(), fmt)
            except Exception:
                continue
        return None

    def _extract_short_tags(self, text: str) -> Dict[str, Any]:
        """短线：抽取 themes / event_tags / number_tags"""
        themes: List[str] = []
        theme_hits: Dict[str, str] = {}
        for theme, patterns in self.short_themes.items():
            for p in patterns:
                m = re.search(p, text, flags=re.IGNORECASE)
                if m:
                    themes.append(theme)
                    theme_hits[theme] = m.group(0)
                    break

        # 去歧义：如果同时命中“智能驾驶/智能网联”，优先归类到智驾而不是“半导体/先进制程”
        # 典型场景：新闻里提到“车载芯片/算法/硬件”，不等于先进制程催化
        if "智能驾驶/智能网联" in themes and "半导体/先进制程" in themes:
            # 只有在明显提到“光刻/EUV/EDA/先进制程/晶圆”等硬逻辑时，才保留半导体题材
            hard_semicon = re.search(
                r"(光刻|EUV|EDA|先进制程|晶圆|12英寸|2nm|3nm|5nm|DRAM|NAND)",
                text,
                flags=re.IGNORECASE,
            )
            if not hard_semicon:
                themes = [t for t in themes if t != "半导体/先进制程"]

        event_tags: List[str] = []
        event_score = 0
        for label, pattern, weight in self.short_event_triggers:
            if re.search(pattern, text):
                event_tags.append(label)
                event_score += weight

        number_tags: List[str] = []
        number_score = 0
        for cre, w in self.short_number_patterns:
            if cre.search(text):
                number_tags.append("含关键数字")
                number_score += w

        return {
            "themes": list(dict.fromkeys(themes)),
            "event_tags": list(dict.fromkeys(event_tags))[:6],
            "event_score": event_score,
            "number_score": number_score,
            "number_tags": list(dict.fromkeys(number_tags)),
            "theme_hits": theme_hits,
        }

    def _fingerprint(self, title: str) -> str:
        """用于去重：尽量把“同一条新闻不同来源/不同措辞”归一到同一桶"""
        if not title:
            return ""
        s = title.lower()
        s = re.sub(r"\s+", "", s)
        s = re.sub(r"[【】\[\]（）\(\)「」《》<>，。！？、:：;；\"'“”‘’·…\-_|/\\]", "", s)
        s = re.sub(r"\d+", "", s)
        # 常见噪声词移除
        s = s.replace("据", "").replace("消息", "").replace("报道", "")
        return s[:80]

    def _apply_shortline_adjustments(
        self,
        base_score: int,
        text: str,
        dt_str: str,
        short_tags: Dict[str, Any],
    ) -> int:
        """短线模式：对 base_score 做时效/事件/噪声等调整"""
        score = base_score

        # 事件触发词/数字加分
        score += short_tags.get("event_score", 0)
        score += short_tags.get("number_score", 0)

        # 时效加分：越接近当前越重要（短线）
        dt = self._parse_datetime(dt_str)
        if dt:
            delta_hours = (datetime.now() - dt).total_seconds() / 3600.0
            if delta_hours <= 6:
                score += 3
            elif delta_hours <= 24:
                score += 2
            elif delta_hours <= 72:
                score += 1

        # 噪声降权：如果强题材命中则不降/少降
        is_noise = any(p.search(text) for p in self.noise_patterns)
        strong_theme = bool(short_tags.get("themes"))
        if is_noise and not strong_theme:
            score = int(score * 0.25)

        # 过度国际花边：如果只命中“其他国家”或外部政治，进一步降权（保留油价/美联储等）
        if re.search(
            r"(总统|抗议|拘捕|扫毒|枪击|内塔尼亚胡|马克龙|普京)",
            text,
        ) and not re.search(r"(油|油气|美联储|美元|关税|贸易|CPI|PPI)", text):
            score = int(score * 0.4)

        return max(0, score)

    def analyze_single_news(self, news: Dict[str, Any]) -> Dict[str, Any]:
        """分析单条新闻"""
        title = news.get('title', '')
        content = news.get('content', '')
        text = (title or '') + ' ' + (content or '')

        # 计算重要性得分
        score = 0
        matched_categories: List[str] = []
        is_other_country = False
        category_weights: Dict[str, int] = {}

        for category_name, config in self.keywords_config.items():
            for keyword in config['keywords']:
                if keyword in text:
                    category = config['category']
                    category_weights[category] = int(config['weight'])
                    matched_categories.append(config['category'])
                    if config['category'] == '其他国家':
                        is_other_country = True
                    break  # 每个分类只计算一次

        # 去重分类（保留首次出现顺序）
        matched_categories = list(dict.fromkeys(matched_categories))

        # short 模式：避免“多分类累加导致虚高”，改为“主线权重 + 少量叠加”
        if self.mode == "short":
            if not category_weights:
                score = 0
            else:
                weights_sorted = sorted(
                    category_weights.values(),
                    reverse=True,
                )
                top = weights_sorted[0]
                second = weights_sorted[1] if len(weights_sorted) > 1 else 0
                # 主线为主，第二条逻辑只给小权重，其他分类只做轻微加分
                extra = min(max(len(weights_sorted) - 2, 0), 3)
                score = int(top + second * 0.3 + extra)
                # 纯海外宏观（没有产业/政策/资金）降权，避免刷屏
                overseas = {'美国影响', '欧盟影响', '日本影响', '国际贸易'}
                if set(matched_categories).issubset(overseas):
                    score = int(score * 0.6)
        else:
            # default 模式：保留原有“多分类累加”
            score = sum(category_weights.values())

        # 如果是其他国家新闻，大幅降低得分（只保留10%权重）
        if is_other_country:
            # 移除其他国家的得分，重新计算其他分类的得分并大幅降权
            other_score = score - 1  # 减去其他国家的1分
            # 其他分类只保留10%权重，加上其他国家的1分
            score = int(other_score * 0.1) + 1
            # 如果最终得分小于3，视为不重要
            if score < 3:
                score = 0

        # 判断利好/利空
        sentiment = self._judge_sentiment(text)

        # 短线增强：事件驱动/时效/噪声过滤
        dt_str = self._safe_get_datetime_str(news)
        if self.mode == "short":
            short_tags = self._extract_short_tags(text)
        else:
            short_tags = {
                "themes": [],
                "event_tags": [],
                "event_score": 0,
                "number_score": 0,
            }
        if self.mode == "short":
            score = self._apply_shortline_adjustments(
                score,
                text,
                dt_str,
                short_tags,
            )

        # 返回分析结果
        return {
            'title': title,
            'time': news.get('time', ''),
            'datetime': dt_str,
            'source': news.get('source', ''),
            'score': score,
            'categories': list(set(matched_categories)),  # 去重
            'sentiment': sentiment,
            'themes': short_tags.get('themes', []),
            'theme_hits': short_tags.get('theme_hits', {}),
            'tags': short_tags.get('event_tags', []),
            'content': content[:240] + '...' if len(content) > 240 else content
        }

    def _judge_sentiment(self, text: str) -> str:
        """判断新闻情绪"""
        # 基础统计
        positive_count = sum(1 for kw in self.positive_keywords if kw in text)
        negative_count = sum(1 for kw in self.negative_keywords if kw in text)

        # 否定词修正：出现“未/不/无/终止/撤回”等否定 + 利好词，视作利空权重更高
        for neg in self.negations:
            for pos in self.positive_keywords:
                if (neg + pos) in text:
                    negative_count += 2
                    positive_count = max(0, positive_count - 1)

        # 典型短线强利好/利空触发
        pos_strong = (
            r"(获批|获准|准入|牌照|首块|首个|首次|中标|订单|定点|签署战略合作|量产|扩产|投产|上修|预增)"
        )
        if re.search(pos_strong, text):
            positive_count += 2
        if re.search(r"(终止|撤回|暂停|下调|处罚|立案|被查|退市|爆雷)", text):
            negative_count += 2

        if positive_count > negative_count:
            return '利好'
        elif negative_count > positive_count:
            return '利空'
        else:
            return '中性'

    def analyze_file(self, json_file: str, min_score: int = 5):
        """分析JSON文件中的新闻"""
        if not os.path.exists(json_file):
            print(f"❌ 文件不存在: {json_file}")
            return

        print(f"\n{'='*80}")
        print(f"分析文件: {os.path.basename(json_file)}")
        print(f"{'='*80}\n")

        # 读取数据
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 支持两种JSON格式
        if isinstance(data, list):
            # 导出文件格式：直接是数组 [...]
            news_list = data
        elif isinstance(data, dict):
            # 原始文件格式：字典 {"news": [...]}
            news_list = data.get('news', [])
        else:
            print("❌ 不支持的JSON格式")
            return []

        print(f"总新闻数: {len(news_list)} 条")
        print(f"分析标准: 重要性得分 >= {min_score}\n")

        # 分析所有新闻
        important_news: List[Dict[str, Any]] = []
        excluded_news: List[Dict[str, Any]] = []  # 被排除的新闻
        for news in news_list:
            result = self.analyze_single_news(news)
            if result['score'] >= min_score:
                important_news.append(result)
            else:
                excluded_news.append(result)

        # 去重（短线非常重要：同一消息多来源会刷屏）
        if self.mode == "short" and important_news:
            important_news = self._deduplicate_news(important_news)

        # 按得分排序
        important_news.sort(key=lambda x: x['score'], reverse=True)
        excluded_news.sort(key=lambda x: x['score'], reverse=True)

        print(f"重要新闻: {len(important_news)} 条")
        print(f"排除新闻: {len(excluded_news)} 条\n")

        # 生成报告
        self._print_report(important_news)

        # 保存报告
        self._save_report(important_news, json_file)

        # 保存被排除的新闻（便于审核）
        self._save_excluded_report(excluded_news, json_file, min_score)

        return important_news

    def _deduplicate_news(
        self,
        news_list: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """按 title 指纹去重：保留最高分，分数相同保留更近时间"""
        buckets: Dict[str, Dict[str, Any]] = {}
        for n in news_list:
            fp = self._fingerprint(n.get("title", ""))
            if not fp:
                fp = n.get("title", "")
            if fp not in buckets:
                buckets[fp] = n
                continue
            old = buckets[fp]
            if n.get("score", 0) > old.get("score", 0):
                buckets[fp] = n
            elif n.get("score", 0) == old.get("score", 0):
                ndt = self._parse_datetime(n.get("datetime", ""))
                odt = self._parse_datetime(old.get("datetime", ""))
                if ndt and odt and ndt > odt:
                    buckets[fp] = n
        return list(buckets.values())

    def _print_report(self, news_list: List[Dict]):
        """打印分析报告"""
        if not news_list:
            print("未发现重要新闻")
            return

        # 按影响级别分组
        critical = [n for n in news_list if n['score'] >= 10]  # 重大影响
        high = [n for n in news_list if 7 <= n['score'] < 10]  # 高影响
        medium = [n for n in news_list if 5 <= n['score'] < 7]  # 中等影响

        # 打印统计
        print("📊 影响级别统计")
        print(f"  🔴 重大影响: {len(critical)} 条")
        print(f"  🟠 高度影响: {len(high)} 条")
        print(f"  🟡 中等影响: {len(medium)} 条")
        print()

        # 打印详细列表
        if critical:
            print("\n" + "="*80)
            print("🔴 重大影响新闻 (得分≥10)")
            print("="*80)
            for i, news in enumerate(critical, 1):
                self._print_news_detail(i, news)

        if high:
            print("\n" + "="*80)
            print("🟠 高度影响新闻 (得分7-9)")
            print("="*80)
            for i, news in enumerate(high, 1):
                self._print_news_detail(i, news)

        if medium:
            print("\n" + "="*80)
            print("🟡 中等影响新闻 (得分5-6)")
            print("="*80)
            for i, news in enumerate(medium, 1):
                self._print_news_detail(i, news)

    def _print_news_detail(self, index: int, news: Dict):
        """打印新闻详情"""
        sentiment_icon = {
            '利好': '📈',
            '利空': '📉',
            '中性': '➡️'
        }

        print(f"\n【{index}】{news['title']}")
        print(f"  ⏰ 时间: {news['datetime']}")
        if news.get('source'):
            print(f"  📰 来源: {news['source']}")
        print(f"  ⭐ 得分: {news['score']}")
        print(f"  🏷️ 分类: {', '.join(news['categories'])}")
        icon = sentiment_icon.get(news['sentiment'], '➡️')
        print(f"  {icon} 影响: {news['sentiment']}")
        if news.get('content'):
            print(f"  📝 摘要: {news['content']}")
        print()

    def _save_report(self, news_list: List[Dict], json_file: str):
        """保存分析报告"""
        if not news_list:
            return

        base_name = os.path.basename(json_file).replace('.json', '')
        report_file = f'data/analysis/{base_name}_重点分析.md'

        # 确保目录存在
        os.makedirs('data/analysis', exist_ok=True)

        lines = []
        lines.append(f"# {base_name} A股重点新闻分析\n")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"**生成时间**: {now_str}\n")
        lines.append(f"**总新闻数**: {len(news_list)} 条\n")
        lines.append(f"**分析模式**: {self.mode}\n")
        lines.append("---\n")

        # 统计信息
        critical = [n for n in news_list if n['score'] >= 10]
        high = [n for n in news_list if 7 <= n['score'] < 10]
        medium = [n for n in news_list if 5 <= n['score'] < 7]

        lines.append("## 📊 影响级别统计\n")
        lines.append(f"- 🔴 **重大影响**: {len(critical)} 条 (得分≥10)")
        lines.append(f"- 🟠 **高度影响**: {len(high)} 条 (得分7-9)")
        lines.append(f"- 🟡 **中等影响**: {len(medium)} 条 (得分5-6)\n")

        # 分类统计
        category_count: Dict[str, int] = {}
        for news in news_list:
            for cat in news['categories']:
                category_count[cat] = category_count.get(cat, 0) + 1

        if category_count:
            lines.append("## 🏷️ 分类统计\n")
            sorted_cats = sorted(
                category_count.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            for cat, count in sorted_cats:
                lines.append(f"- **{cat}**: {count} 条")
            lines.append("\n")

        # 情绪统计
        sentiment_count: Dict[str, int] = {}
        for news in news_list:
            sent = news['sentiment']
            sentiment_count[sent] = sentiment_count.get(sent, 0) + 1

        lines.append("## 📈 情绪分析\n")
        lines.append(f"- 📈 **利好**: {sentiment_count.get('利好', 0)} 条")
        lines.append(f"- 📉 **利空**: {sentiment_count.get('利空', 0)} 条")
        lines.append(f"- ➡️ **中性**: {sentiment_count.get('中性', 0)} 条\n")

        lines.append("---\n")

        # 短线：题材热度 Top
        if self.mode == "short":
            theme_count: Dict[str, int] = defaultdict(int)
            for n in news_list:
                for t in n.get("themes", []) or []:
                    theme_count[t] += 1
            if theme_count:
                lines.append("## 🔥 短线题材热度 Top\n")
                for theme, cnt in sorted(
                    theme_count.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:12]:
                    lines.append(f"- **{theme}**: {cnt} 条")

                # 把题材Top的“代表新闻（含具体内容摘要）”放在重大影响新闻之前
                lines.append("\n## 🧩 题材热度 Top（代表新闻）\n")

                def _news_sort_key(x: Dict[str, Any]):
                    dt = self._parse_datetime(x.get("datetime", ""))
                    # dt 为空时用最小值，确保排序稳定
                    dt_key = dt or datetime.min
                    return (int(x.get("score", 0)), dt_key)

                top_themes = [
                    theme
                    for theme, _cnt in sorted(
                        theme_count.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:12]
                ]

                for theme in top_themes:
                    related = [
                        n for n in news_list
                        if theme in (n.get("themes") or [])
                    ]
                    if not related:
                        continue
                    related.sort(key=_news_sort_key, reverse=True)
                    lines.append(f"### {theme}\n")
                    # 每个题材展示全部相关新闻（便于人工校正分类）
                    for n in related:
                        title = n.get("title", "")
                        dt_str = n.get("datetime", "")
                        score = n.get("score", 0)
                        tags = " | ".join(n.get("tags") or [])
                        theme_hit = ""
                        hits = n.get("theme_hits") or {}
                        if isinstance(hits, dict):
                            theme_hit = str(hits.get(theme, "")).strip()
                        summary = (
                            (n.get("content") or "")
                            .replace("\n", " ")
                            .strip()
                        )
                        if len(summary) > 260:
                            summary = summary[:260] + "..."
                        lines.append(
                            f"- **{score}分** | **{dt_str}** | {title}"
                        )
                        if tags:
                            lines.append(f"  - **触发词**: {tags}")
                        if theme_hit:
                            lines.append(f"  - **命中词**: {theme_hit}")
                        if summary:
                            lines.append(f"  - **内容摘要**: {summary}")
                    lines.append("")

                lines.append("---\n")

        # 详细列表
        if critical:
            lines.append("## 🔴 重大影响新闻\n")
            for i, news in enumerate(critical, 1):
                lines.extend(self._format_news_md(i, news))

        if high:
            lines.append("## 🟠 高度影响新闻\n")
            for i, news in enumerate(high, 1):
                lines.extend(self._format_news_md(i, news))

        if medium:
            lines.append("## 🟡 中等影响新闻\n")
            for i, news in enumerate(medium, 1):
                lines.extend(self._format_news_md(i, news))

        # 保存
        report_content = "\n".join(lines)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"✅ 分析报告已保存: {report_file}\n")

    def _save_excluded_report(
        self,
        excluded_news: List[Dict[str, Any]],
        json_file: str,
        min_score: int,
    ):
        """保存被排除的新闻，便于人工审核排除是否合理"""
        if not excluded_news:
            return

        base_name = os.path.basename(json_file).replace('.json', '')
        report_file = f'data/analysis/{base_name}_排除新闻.md'

        # 确保目录存在
        os.makedirs('data/analysis', exist_ok=True)

        lines = []
        lines.append(f"# {base_name} 被排除新闻列表\n")
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"**生成时间**: {now_str}\n")
        lines.append(f"**排除阈值**: 得分 < {min_score}\n")
        lines.append(f"**排除数量**: {len(excluded_news)} 条\n")
        lines.append(f"**分析模式**: {self.mode}\n")
        lines.append("\n> ⚠️ 本文件用于审核排除是否合理，")
        lines.append("如发现重要新闻被误排除，请调整关键词权重或阈值。\n")
        lines.append("---\n")

        # 按得分分组统计
        score_groups: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for news in excluded_news:
            score_groups[news['score']].append(news)

        # 得分分布统计
        lines.append("## 📊 得分分布统计\n")
        for score in sorted(score_groups.keys(), reverse=True):
            count = len(score_groups[score])
            lines.append(f"- **得分 {score}**: {count} 条")
        lines.append("\n---\n")

        # 分类统计
        category_count: Dict[str, int] = defaultdict(int)
        for news in excluded_news:
            for cat in news.get('categories', []):
                category_count[cat] += 1
            if not news.get('categories'):
                category_count['未分类'] += 1

        lines.append("## 🏷️ 分类统计\n")
        sorted_cats = sorted(
            category_count.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        for cat, count in sorted_cats[:15]:
            lines.append(f"- **{cat}**: {count} 条")
        lines.append("\n---\n")

        # 题材统计（短线模式）
        if self.mode == "short":
            theme_count: Dict[str, int] = defaultdict(int)
            for news in excluded_news:
                for theme in news.get('themes', []) or []:
                    theme_count[theme] += 1
            if theme_count:
                lines.append("## 🔥 题材统计（被排除）\n")
                for theme, cnt in sorted(
                    theme_count.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]:
                    lines.append(f"- **{theme}**: {cnt} 条")
                lines.append("\n---\n")

        # 详细列表：按得分从高到低分组展示
        lines.append("## 📋 被排除新闻详情\n")
        lines.append("> 按得分从高到低排列，优先审核高分被排除的新闻\n")

        for score in sorted(score_groups.keys(), reverse=True):
            news_in_group = score_groups[score]
            lines.append(f"\n### 得分 {score} ({len(news_in_group)} 条)\n")

            for i, news in enumerate(news_in_group, 1):
                title = news.get('title', '')
                dt_str = news.get('datetime', '')
                source = news.get('source', '')
                categories = news.get('categories', [])
                themes = news.get('themes', [])
                tags = news.get('tags', [])
                sentiment = news.get('sentiment', '中性')
                raw_content = news.get('content') or ''
                content = raw_content.replace('\n', ' ').strip()
                if len(content) > 200:
                    content = content[:200] + '...'

                lines.append(f"**{i}.** {title}")
                lines.append(f"  - ⏰ {dt_str} | 📰 {source}")
                if categories:
                    lines.append(f"  - 🏷️ 分类: {' | '.join(categories)}")
                if themes:
                    lines.append(f"  - 📌 题材: {' | '.join(themes)}")
                if tags:
                    lines.append(f"  - 🔖 触发词: {' | '.join(tags)}")
                lines.append(f"  - 📊 情绪: {sentiment}")
                if content:
                    lines.append(f"  - 📝 {content}")
                lines.append("")

        # 保存文件
        report_content = "\n".join(lines)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"✅ 排除新闻已保存: {report_file}")

    def _format_news_md(self, index: int, news: Dict) -> List[str]:
        """格式化新闻为Markdown"""
        sentiment_icon = {
            '利好': '📈',
            '利空': '📉',
            '中性': '➡️'
        }

        lines = []
        lines.append(f"### {index}. {news['title']}\n")
        lines.append(f"- **时间**: {news['datetime']}")
        lines.append(f"- **来源**: {news['source']}")
        lines.append(f"- **得分**: ⭐ {news['score']}")
        lines.append(f"- **分类**: {' | '.join(news['categories'])}")
        if news.get("themes"):
            lines.append(f"- **题材**: {' | '.join(news.get('themes') or [])}")
        if news.get("tags"):
            lines.append(f"- **触发词**: {' | '.join(news.get('tags') or [])}")
        icon = sentiment_icon.get(news['sentiment'], '➡️')
        lines.append(f"- **影响**: {icon} {news['sentiment']}")

        if news.get('content'):
            lines.append(f"\n{news['content']}\n")

        lines.append("---\n")
        return lines

    def analyze_all_files(self, min_score: int = 5):
        """分析所有JSON文件"""
        raw_dir = 'data/raw'

        if not os.path.exists(raw_dir):
            print(f"❌ 目录不存在: {raw_dir}")
            return

        json_files = sorted(
            [f for f in os.listdir(raw_dir) if f.endswith('.json')]
        )

        if not json_files:
            print("❌ 未找到JSON文件")
            return

        print(f"\n找到 {len(json_files)} 个JSON文件")
        print("开始批量分析...\n")

        for filename in json_files:
            filepath = os.path.join(raw_dir, filename)
            self.analyze_file(filepath, min_score)
            print()


def main():
    """主函数"""
    analyzer = NewsImpactAnalyzer()

    import sys

    if len(sys.argv) > 1:
        # 分析指定文件
        json_file = sys.argv[1]
        min_score = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        analyzer.analyze_file(json_file, min_score)
    else:
        # 分析所有文件
        print("\n" + "="*80)
        print("A股新闻影响分析助手")
        print("="*80)
        print("\n请选择:")
        print("1. 分析所有文件")
        print("2. 分析最新文件")
        print("3. 退出")

        choice = input("\n请输入选项 (1/2/3): ").strip()

        if choice == '1':
            min_score = input("最低得分 (默认5): ").strip()
            min_score = int(min_score) if min_score else 5
            analyzer.analyze_all_files(min_score)
        elif choice == '2':
            raw_dir = 'data/raw'
            json_files = sorted(
                [f for f in os.listdir(raw_dir) if f.endswith('.json')]
            )
            if json_files:
                latest_file = os.path.join(raw_dir, json_files[-1])
                min_score = input("最低得分 (默认5): ").strip()
                min_score = int(min_score) if min_score else 5
                analyzer.analyze_file(latest_file, min_score)
            else:
                print("❌ 未找到JSON文件")
        else:
            print("退出")


if __name__ == "__main__":
    main()
