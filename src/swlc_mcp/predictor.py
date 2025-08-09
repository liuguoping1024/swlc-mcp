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
    
    def __init__(self):
        self.rules = {
            'ssq': {'red_count': 6, 'red_range': (1, 33), 'blue_count': 1, 'blue_range': (1, 16)},
            '3d': {'count': 3, 'range': (0, 9)},
            'qlc': {'red_count': 7, 'red_range': (1, 30), 'blue_count': 1, 'blue_range': (1, 30)},
            'kl8': {'count': 20, 'range': (1, 80)}
        }
    
    def predict(self, lottery_type: str, historical_data: List[Dict], count: int = 5) -> List[PredictionResult]:
        """基于历史数据的规则预测"""
        if lottery_type not in self.rules:
            raise ValueError(f"不支持的彩票类型: {lottery_type}")
        
        results = []
        number_freq = self._analyze_frequency(historical_data, lottery_type)
        hot_numbers = self._get_hot_numbers(number_freq, lottery_type)
        cold_numbers = self._get_cold_numbers(number_freq, lottery_type)
        
        for i in range(count):
            if lottery_type == 'ssq':
                prediction = self._predict_ssq(hot_numbers, cold_numbers)
            elif lottery_type == '3d':
                prediction = self._predict_3d(hot_numbers, cold_numbers)
            elif lottery_type == 'qlc':
                prediction = self._predict_qlc(hot_numbers, cold_numbers)
            elif lottery_type == 'kl8':
                prediction = self._predict_kl8(hot_numbers, cold_numbers)
            else:
                continue
            
            confidence = self._calculate_confidence(prediction, historical_data)
            
            results.append(PredictionResult(
                numbers=prediction['numbers'],
                special_numbers=prediction.get('special_numbers'),
                confidence=confidence,
                method='rule',
                timestamp=datetime.now().isoformat(),
                metadata={'hot_numbers': hot_numbers[:5], 'cold_numbers': cold_numbers[:5]}
            ))
        
        return results
    
    def _analyze_frequency(self, historical_data: List[Dict], lottery_type: str) -> Dict[str, int]:
        """分析号码频率"""
        frequency = {}
        for data in historical_data:
            numbers = data.get('numbers', [])
            for num in numbers:
                frequency[num] = frequency.get(num, 0) + 1
        return frequency
    
    def _get_hot_numbers(self, frequency: Dict[str, int], lottery_type: str) -> List[str]:
        """获取热门号码"""
        sorted_numbers = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        return [num for num, _ in sorted_numbers]
    
    def _get_cold_numbers(self, frequency: Dict[str, int], lottery_type: str) -> List[str]:
        """获取冷门号码"""
        all_numbers = set()
        if lottery_type == 'ssq':
            all_numbers = set(str(i).zfill(2) for i in range(1, 34))
        elif lottery_type == '3d':
            all_numbers = set(str(i) for i in range(10))
        elif lottery_type == 'qlc':
            all_numbers = set(str(i).zfill(2) for i in range(1, 31))
        elif lottery_type == 'kl8':
            all_numbers = set(str(i).zfill(2) for i in range(1, 81))
        
        appeared_numbers = set(frequency.keys())
        cold_numbers = list(all_numbers - appeared_numbers)
        random.shuffle(cold_numbers)
        return cold_numbers
    
    def _predict_ssq(self, hot_numbers: List[str], cold_numbers: List[str]) -> Dict:
        """预测双色球"""
        red_numbers = []
        red_numbers.extend(hot_numbers[:3])
        red_numbers.extend(cold_numbers[:3])
        red_numbers = red_numbers[:6]
        
        blue_numbers = hot_numbers[:5] if hot_numbers else [str(i).zfill(2) for i in range(1, 17)]
        blue_number = random.choice(blue_numbers)
        
        return {
            'numbers': sorted(red_numbers, key=int),
            'special_numbers': [blue_number]
        }
    
    def _predict_3d(self, hot_numbers: List[str], cold_numbers: List[str]) -> Dict:
        """预测福彩3D"""
        numbers = []
        numbers.extend(hot_numbers[:2])
        numbers.extend(cold_numbers[:1])
        numbers = numbers[:3]
        
        while len(numbers) < 3:
            num = str(random.randint(0, 9))
            if num not in numbers:
                numbers.append(num)
        
        return {'numbers': numbers}
    
    def _predict_qlc(self, hot_numbers: List[str], cold_numbers: List[str]) -> Dict:
        """预测七乐彩"""
        red_numbers = []
        red_numbers.extend(hot_numbers[:4])
        red_numbers.extend(cold_numbers[:3])
        red_numbers = red_numbers[:7]
        
        blue_numbers = hot_numbers[:5] if hot_numbers else [str(i).zfill(2) for i in range(1, 31)]
        blue_number = random.choice(blue_numbers)
        
        return {
            'numbers': sorted(red_numbers, key=int),
            'special_numbers': [blue_number]
        }
    
    def _predict_kl8(self, hot_numbers: List[str], cold_numbers: List[str]) -> Dict:
        """预测快乐8"""
        numbers = []
        numbers.extend(hot_numbers[:10])
        numbers.extend(cold_numbers[:10])
        numbers = numbers[:20]
        
        while len(numbers) < 20:
            num = str(random.randint(1, 80)).zfill(2)
            if num not in numbers:
                numbers.append(num)
        
        return {'numbers': sorted(numbers, key=int)}
    
    def _calculate_confidence(self, prediction: Dict, historical_data: List[Dict]) -> float:
        """计算预测置信度"""
        if not historical_data:
            return 0.5
        
        numbers = prediction['numbers']
        special_numbers = prediction.get('special_numbers', [])
        all_numbers = numbers + special_numbers
        
        total_appearances = 0
        for data in historical_data:
            historical_numbers = data.get('numbers', []) + data.get('special_numbers', [])
            for num in all_numbers:
                if num in historical_numbers:
                    total_appearances += 1
        
        confidence = min(0.9, max(0.1, total_appearances / (len(historical_data) * len(all_numbers))))
        return round(confidence, 2)

class PredictionManager:
    """预测管理器"""
    
    def __init__(self):
        self.rule_predictor = RuleBasedPredictor()
    
    async def predict(self, lottery_type: str, historical_data: List[Dict], 
                     method: str = 'rule', count: int = 5) -> List[PredictionResult]:
        """执行预测"""
        try:
            if method == 'rule':
                return self.rule_predictor.predict(lottery_type, historical_data, count)
            else:
                # 暂时只支持规则预测
                return self.rule_predictor.predict(lottery_type, historical_data, count)
                
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return self.rule_predictor.predict(lottery_type, historical_data, count)
