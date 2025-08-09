"""
回测引擎模块
提供历史数据回测功能，评估预测算法的准确性
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .predictor import PredictionManager

logger = logging.getLogger(__name__)

@dataclass
class BacktestResult:
    """回测结果"""
    period: str
    actual_numbers: List[str]
    actual_special_numbers: Optional[List[str]] = None
    predictions: List[Dict[str, Any]] = None
    accuracy: float = 0.0
    method: str = ""

@dataclass
class BacktestSummary:
    """回测摘要"""
    total_periods: int
    average_accuracy: float
    best_strategy: str
    strategy_performance: Dict[str, float]
    chart_data: Dict[str, Any]
    timestamp: str

class BacktestEngine:
    """回测引擎"""
    
    def __init__(self):
        self.prediction_manager = PredictionManager()
        self.methods = ['rule']
    
    async def run_backtest(self, lottery_type: str, historical_data: List[Dict], 
                          window_size: int = 100, step: int = 50) -> BacktestSummary:
        """运行回测"""
        try:
            if len(historical_data) < window_size:
                raise ValueError(f"历史数据不足，需要至少{window_size}期数据")
            
            results = []
            chart_data = {
                'periods': [],
                'accuracy': [],
                'precision': []
            }
            
            # 滑动窗口回测
            for start_idx in range(0, len(historical_data) - window_size, step):
                end_idx = start_idx + window_size
                test_period = start_idx + window_size
                
                if test_period >= len(historical_data):
                    break
                
                # 训练数据（历史数据）
                train_data = historical_data[start_idx:end_idx]
                # 测试数据（目标期）
                test_data = historical_data[test_period]
                
                # 为每个方法生成预测
                method_results = {}
                for method in self.methods:
                    try:
                        predictions = await self.prediction_manager.predict(
                            lottery_type, train_data, method=method, count=5
                        )
                        
                        # 计算预测准确性
                        accuracy = self._calculate_prediction_accuracy(
                            predictions, test_data, lottery_type
                        )
                        
                        method_results[method] = {
                            'predictions': predictions,
                            'accuracy': accuracy
                        }
                        
                    except Exception as e:
                        logger.error(f"方法{method}预测失败: {e}")
                        method_results[method] = {
                            'predictions': [],
                            'accuracy': 0.0
                        }
                
                # 记录结果
                period_result = BacktestResult(
                    period=test_data.get('period', f'Period_{test_period}'),
                    actual_numbers=test_data.get('numbers', []),
                    actual_special_numbers=test_data.get('special_numbers'),
                    predictions=method_results,
                    accuracy=max([r['accuracy'] for r in method_results.values()]),
                    method=max(method_results.items(), key=lambda x: x[1]['accuracy'])[0]
                )
                
                results.append(period_result)
                
                # 更新图表数据
                chart_data['periods'].append(period_result.period)
                chart_data['accuracy'].append(period_result.accuracy)
                chart_data['precision'].append(self._calculate_precision(method_results))
            
            # 生成摘要
            summary = self._generate_summary(results, chart_data)
            
            return summary
            
        except Exception as e:
            logger.error(f"回测失败: {e}")
            raise
    
    def _calculate_prediction_accuracy(self, predictions: List, actual_data: Dict, 
                                     lottery_type: str) -> float:
        """计算预测准确性"""
        if not predictions:
            return 0.0
        
        actual_numbers = actual_data.get('numbers', [])
        actual_special_numbers = actual_data.get('special_numbers', [])
        
        best_accuracy = 0.0
        
        for prediction in predictions:
            pred_numbers = prediction.numbers
            pred_special_numbers = prediction.special_numbers or []
            
            # 计算红球命中数
            red_hits = len(set(pred_numbers) & set(actual_numbers))
            
            # 计算蓝球命中数
            blue_hits = 0
            if pred_special_numbers and actual_special_numbers:
                blue_hits = len(set(pred_special_numbers) & set(actual_special_numbers))
            
            # 根据彩票类型计算准确性
            if lottery_type == 'ssq':
                accuracy = self._calculate_ssq_accuracy(red_hits, blue_hits)
            elif lottery_type == '3d':
                accuracy = self._calculate_3d_accuracy(pred_numbers, actual_numbers)
            elif lottery_type == 'qlc':
                accuracy = self._calculate_qlc_accuracy(red_hits, blue_hits)
            elif lottery_type == 'kl8':
                accuracy = self._calculate_kl8_accuracy(pred_numbers, actual_numbers)
            else:
                accuracy = red_hits / len(actual_numbers) if actual_numbers else 0.0
            
            best_accuracy = max(best_accuracy, accuracy)
        
        return round(best_accuracy, 4)
    
    def _calculate_ssq_accuracy(self, red_hits: int, blue_hits: int) -> float:
        """计算双色球准确性"""
        red_accuracy = red_hits / 6.0
        blue_accuracy = blue_hits / 1.0
        return red_accuracy * 0.8 + blue_accuracy * 0.2
    
    def _calculate_3d_accuracy(self, pred_numbers: List[str], actual_numbers: List[str]) -> float:
        """计算福彩3D准确性"""
        if len(pred_numbers) != 3 or len(actual_numbers) != 3:
            return 0.0
        
        hits = 0
        for i in range(3):
            if pred_numbers[i] == actual_numbers[i]:
                hits += 1
        
        return hits / 3.0
    
    def _calculate_qlc_accuracy(self, red_hits: int, blue_hits: int) -> float:
        """计算七乐彩准确性"""
        red_accuracy = red_hits / 7.0
        blue_accuracy = blue_hits / 1.0
        return red_accuracy * 0.8 + blue_accuracy * 0.2
    
    def _calculate_kl8_accuracy(self, pred_numbers: List[str], actual_numbers: List[str]) -> float:
        """计算快乐8准确性"""
        hits = len(set(pred_numbers) & set(actual_numbers))
        return hits / 20.0
    
    def _calculate_precision(self, method_results: Dict[str, Dict]) -> float:
        """计算精确度"""
        if not method_results:
            return 0.0
        
        accuracies = [result['accuracy'] for result in method_results.values()]
        return sum(accuracies) / len(accuracies)
    
    def _generate_summary(self, results: List[BacktestResult], 
                         chart_data: Dict[str, Any]) -> BacktestSummary:
        """生成回测摘要"""
        if not results:
            return BacktestSummary(
                total_periods=0,
                average_accuracy=0.0,
                best_strategy="",
                strategy_performance={},
                chart_data=chart_data,
                timestamp=datetime.now().isoformat()
            )
        
        total_periods = len(results)
        average_accuracy = sum(r.accuracy for r in results) / total_periods
        
        strategy_performance = {}
        for method in self.methods:
            method_results = [r for r in results if r.method == method]
            if method_results:
                strategy_performance[method] = sum(r.accuracy for r in method_results) / len(method_results)
            else:
                strategy_performance[method] = 0.0
        
        best_strategy = max(strategy_performance.items(), key=lambda x: x[1])[0]
        
        return BacktestSummary(
            total_periods=total_periods,
            average_accuracy=round(average_accuracy, 4),
            best_strategy=best_strategy,
            strategy_performance=strategy_performance,
            chart_data=chart_data,
            timestamp=datetime.now().isoformat()
        )
