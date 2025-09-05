"""
彩票预测算法模块
提供多种预测算法：规则算法、AI算法、混合算法
"""

import random
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class PredictionResult:
    """预测结果"""
    numbers: List[str]
    special_numbers: Optional[List[str]] = None
    confidence: float = 0.0
    method: str = "rule"
    timestamp: str = ""
    metadata: Dict[str, Any] = None

class RuleBasedPredictor:
    """基于规则的预测算法"""
    
    def predict(self, lottery_type: str, historical_data: List[Dict], count: int = 5, strategy: Optional[str] = None) -> List[PredictionResult]:
        """基于历史数据的规则预测，支持策略"""
        if lottery_type not in {"ssq", "3d", "qlc", "kl8", "双色球", "福彩3D", "七乐彩", "快乐8"}:
            raise ValueError(f"不支持的彩票类型: {lottery_type}")
        
        # 仅实现双色球策略，其它类型先回退到简单规则
        if lottery_type in ("ssq", "双色球"):
            return self._predict_ssq_with_strategies(historical_data, strategy, count)
        
        # 非双色球回退：简单随机+频率权重
        return self._predict_fallback(historical_data, count)
    
    def _predict_ssq_with_strategies(self, historical_data: List[Dict], strategy: Optional[str], count: int) -> List[PredictionResult]:
        # 计算频次
        freq: Dict[str, int] = {}
        blue_freq: Dict[str, int] = {}
        for d in historical_data:
            for n in d.get('numbers', []):
                freq[n] = freq.get(n, 0) + 1
            for n in (d.get('special_numbers') or []):
                blue_freq[n] = blue_freq.get(n, 0) + 1
        # 归一化全集
        all_red = [f"{i:02d}" for i in range(1, 34)]
        for n in all_red:
            freq.setdefault(n, 0)
        all_blue = [f"{i:02d}" for i in range(1, 17)]
        for n in all_blue:
            blue_freq.setdefault(n, 0)
        
        hot = sorted(freq.items(), key=lambda x: (-x[1], int(x[0])))
        cold = sorted(freq.items(), key=lambda x: (x[1], int(x[0])))
        medium = [k for k, v in sorted(freq.items(), key=lambda x: (abs(x[1] - (sum(freq.values())/len(freq) if freq else 0)), int(x[0])))]
        blue_sorted = sorted(blue_freq.items(), key=lambda x: (-x[1], int(x[0])))
        
        def pick_distinct(candidates: List[str], k: int, exclude: Optional[set] = None) -> List[str]:
            res = []
            seen = set(exclude or set())
            for n in candidates:
                if n in seen:
                    continue
                res.append(n)
                seen.add(n)
                if len(res) >= k:
                    break
            # 不足则随机补齐
            if len(res) < k:
                pool = [x for x in all_red if x not in seen]
                random.shuffle(pool)
                res.extend(pool[:(k - len(res))])
            return sorted(res, key=lambda x: int(x))
        
        def blue_pick(top_k: int = 4) -> str:
            pool = [b for b, _ in blue_sorted[:top_k]] or all_blue
            return random.choice(pool)
        
        strategies = {
            'balanced': '热冷均衡型',
            'cold_recovery': '冷门回补型',
            'hot_focus': '热门集中型',
            'interval_balance': '区间平衡型',
            'contrarian': '反向思维型'
        }
        
        results: List[PredictionResult] = []
        to_run: List[str]
        if strategy in (None, '', 'all'):
            to_run = ['balanced', 'cold_recovery', 'hot_focus', 'interval_balance', 'contrarian']
        else:
            to_run = [strategy]
        
        for strat in to_run:
            if strat == 'balanced':
                red = pick_distinct([k for k, _ in hot] + [k for k, _ in cold], 6)
            elif strat == 'cold_recovery':
                red = pick_distinct([k for k, _ in cold] + medium + [k for k, _ in hot], 6)
            elif strat == 'hot_focus':
                red = pick_distinct([k for k, _ in hot] + medium, 6)
            elif strat == 'interval_balance':
                # 每区间各取2个：1-11,12-22,23-33，优先中频次
                seg1 = [n for n in medium if 1 <= int(n) <= 11] + [k for k, _ in hot if 1 <= int(k) <= 11]
                seg2 = [n for n in medium if 12 <= int(n) <= 22] + [k for k, _ in hot if 12 <= int(k) <= 22]
                seg3 = [n for n in medium if 23 <= int(n) <= 33] + [k for k, _ in hot if 23 <= int(k) <= 33]
                r1 = pick_distinct(seg1, 2)
                r2 = pick_distinct(seg2, 2, exclude=set(r1))
                r3 = pick_distinct(seg3, 2, exclude=set(r1 + r2))
                red = sorted(list(set(r1 + r2 + r3)), key=lambda x: int(x))
            elif strat == 'contrarian':
                # 避开最热与连号，偏向冷门与分散
                base = [k for k, _ in cold] + medium
                cand = []
                for n in base:
                    if cand and int(n) == int(cand[-1]) + 1:
                        continue
                    cand.append(n)
                red = pick_distinct(cand, 6)
            else:
                red = pick_distinct([k for k, _ in hot] + [k for k, _ in cold], 6)
            blue = blue_pick()
            results.append(PredictionResult(
                numbers=red,
                special_numbers=[blue],
                confidence=0.0,
                method=strategies.get(strat, strat),
                timestamp=datetime.now().isoformat(),
                metadata={"strategy": strat}
            ))
        
        # 若用户只选单一策略且需要多组，生成该策略的多个变体
        if strategy not in (None, '', 'all') and len(results) < count:
            extra_needed = count - len(results)
            for i in range(extra_needed):
                # 为同一策略生成不同的变体，增加随机性
                if strategy == 'balanced':
                    # 热冷均衡型：调整热门和冷门的比例
                    hot_ratio = 0.3 + (i * 0.1)  # 0.3, 0.4, 0.5, 0.6, 0.7
                    hot_count = max(1, min(5, int(6 * hot_ratio)))
                    cold_count = 6 - hot_count
                    red = pick_distinct([k for k, _ in hot][:hot_count*2] + [k for k, _ in cold][:cold_count*2], 6)
                elif strategy == 'cold_recovery':
                    # 冷门回补型：调整冷门比例
                    cold_ratio = 0.4 + (i * 0.1)  # 0.4, 0.5, 0.6, 0.7, 0.8
                    cold_count = max(2, min(5, int(6 * cold_ratio)))
                    hot_count = 6 - cold_count
                    red = pick_distinct([k for k, _ in cold][:cold_count*2] + [k for k, _ in hot][:hot_count*2], 6)
                elif strategy == 'hot_focus':
                    # 热门集中型：调整热门比例
                    hot_ratio = 0.5 + (i * 0.1)  # 0.5, 0.6, 0.7, 0.8, 0.9
                    hot_count = max(3, min(6, int(6 * hot_ratio)))
                    cold_count = 6 - hot_count
                    red = pick_distinct([k for k, _ in hot][:hot_count*2] + [k for k, _ in cold][:cold_count*2], 6)
                elif strategy == 'interval_balance':
                    # 区间平衡型：调整各区间的数量
                    seg1_count = 2 + (i % 2)  # 2或3
                    seg2_count = 2 + ((i + 1) % 2)  # 2或3
                    seg3_count = 6 - seg1_count - seg2_count
                    seg1 = [n for n in medium if 1 <= int(n) <= 11] + [k for k, _ in hot if 1 <= int(k) <= 11]
                    seg2 = [n for n in medium if 12 <= int(n) <= 22] + [k for k, _ in hot if 12 <= int(k) <= 22]
                    seg3 = [n for n in medium if 23 <= int(n) <= 33] + [k for k, _ in hot if 23 <= int(k) <= 33]
                    r1 = pick_distinct(seg1, seg1_count)
                    r2 = pick_distinct(seg2, seg2_count, exclude=set(r1))
                    r3 = pick_distinct(seg3, seg3_count, exclude=set(r1 + r2))
                    red = sorted(list(set(r1 + r2 + r3)), key=lambda x: int(x))
                elif strategy == 'contrarian':
                    # 反向思维型：调整避开热门的程度
                    avoid_hot_ratio = 0.3 + (i * 0.1)  # 0.3, 0.4, 0.5, 0.6, 0.7
                    avoid_count = int(len(hot) * avoid_hot_ratio)
                    avoid_set = set([k for k, _ in hot[:avoid_count]])
                    base = [k for k, _ in cold if k not in avoid_set] + [k for k, _ in medium if k not in avoid_set]
                    red = pick_distinct(base, 6)
                else:
                    # 默认策略的变体
                    jitter = [k for k, _ in hot][:10] + [k for k, _ in cold][:10]
                    random.shuffle(jitter)
                    red = pick_distinct(jitter, 6)
                
                blue = blue_pick()
                results.append(PredictionResult(
                    numbers=red,
                    special_numbers=[blue],
                    confidence=0.0,
                    method=strategies.get(strategy, strategy),
                    timestamp=datetime.now().isoformat(),
                    metadata={"strategy": strategy, "variant": i + 1}
                ))
        return results
    
    def _predict_fallback(self, historical_data: List[Dict], count: int) -> List[PredictionResult]:
        results: List[PredictionResult] = []
        for _ in range(count):
            numbers = sorted(random.sample(range(1, 34), 6))
            blue = random.randint(1, 16)
            results.append(PredictionResult(
                numbers=[f"{n:02d}" for n in numbers],
                special_numbers=[f"{blue:02d}"],
                confidence=0.0,
                method='rule',
                timestamp=datetime.now().isoformat(),
                metadata={"fallback": True}
            ))
        return results

class PredictionManager:
    """预测管理器"""
    
    def __init__(self):
        self.rule_predictor = RuleBasedPredictor()
    
    async def predict(self, lottery_type: str, historical_data: List[Dict], 
                     method: str = 'rule', count: int = 5, strategy: Optional[str] = None) -> List[PredictionResult]:
        """执行预测"""
        try:
            # 目前仅实现规则+策略
            return self.rule_predictor.predict(lottery_type, historical_data, count=count, strategy=strategy)
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return self.rule_predictor.predict(lottery_type, historical_data, count=count, strategy=strategy)
