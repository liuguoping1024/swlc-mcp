"""
SWLC MCP Server

提供上海地区彩票信息查询服务，包括：
- 双色球开奖查询
- 福彩3D开奖查询  
- 七乐彩开奖查询
- 彩票分析工具
- 号码统计功能
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import re

import httpx
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel

# 导入数据库模块
from .database import LotteryDatabase
# 导入预测和回测模块
from .predictor import PredictionManager
from .backtest import BacktestEngine

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据模型
@dataclass
class LotteryResult:
    """彩票开奖结果"""
    lottery_type: str
    period: str
    draw_date: str
    numbers: List[str]
    special_numbers: Optional[List[str]] = None
    prize_pool: Optional[str] = None
    sales_amount: Optional[str] = None

class LotteryAnalysis(BaseModel):
    """彩票分析结果"""
    hot_numbers: List[str]
    cold_numbers: List[str]
    frequency_stats: Dict[str, int]
    consecutive_analysis: Dict[str, Any]

# 彩票数据服务
class SWLCService:
    """SWLC彩票数据服务"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.cwl.gov.cn/",
                "Accept": "application/json, text/plain, */*",
            },
        )
        self.base_url = 'https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice'
        self.lottery_codes = {
            '双色球': 'ssq',
            '福彩3D': '3d', 
            '七乐彩': 'qlc',
            '快乐8': 'kl8'
        }
        # 初始化数据库
        self.db = LotteryDatabase()
        # 初始化预测和回测引擎
        self.prediction_manager = PredictionManager()
        self.backtest_engine = BacktestEngine()
    
    async def _fetch_lottery_data(self, lottery_type: str, page_size: int = 1) -> Optional[dict]:
        """通用的彩票数据获取方法"""
        try:
            lottery_code = self.lottery_codes.get(lottery_type)
            if not lottery_code:
                logger.error(f"不支持的彩票类型: {lottery_type}")
                return None
            
            params = {
                'name': lottery_code,
                'pageNo': 1,
                'pageSize': page_size,
                'systemType': 'PC'
            }
            
            response = await self.client.get(self.base_url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get('state') == 0 and data.get('result'):
                    return data
            
            return None
        except Exception as e:
            logger.error(f"获取{lottery_type}数据失败: {e}")
            return None
    
    def _is_data_fresh(self, draw_date: str, lottery_type: str) -> bool:
        """
        检查数据是否新鲜（是否需要更新）
        
        Args:
            draw_date: 开奖日期字符串 (格式: "2024-01-01" 或 "2024-01-01(日)")
            lottery_type: 彩票类型
            
        Returns:
            bool: True表示数据新鲜，False表示需要更新
        """
        try:
            # 处理日期格式，移除星期信息
            clean_date = draw_date.split('(')[0] if '(' in draw_date else draw_date
            
            # 解析开奖日期
            draw_datetime = datetime.strptime(clean_date, "%Y-%m-%d")
            current_datetime = datetime.now()
            
            # 计算天数差
            days_diff = (current_datetime - draw_datetime).days
            
            # 根据彩票类型设置不同的更新策略
            if lottery_type == "双色球":
                # 双色球每周二、四、日开奖，如果超过3天没有新数据，认为需要更新
                return days_diff <= 3
            elif lottery_type == "福彩3D":
                # 福彩3D每天开奖，如果超过1天没有新数据，认为需要更新
                return days_diff <= 1
            elif lottery_type == "七乐彩":
                # 七乐彩每周一、三、五开奖，如果超过3天没有新数据，认为需要更新
                return days_diff <= 3
            elif lottery_type == "快乐8":
                # 快乐8每天开奖，如果超过1天没有新数据，认为需要更新
                return days_diff <= 1
            else:
                # 默认策略：超过2天认为需要更新
                return days_diff <= 2
                
        except Exception as e:
            logger.warning(f"检查数据新鲜度失败: {e}")
            # 如果解析失败，保守起见认为需要更新
            return False
    
    def _should_update_from_network(self, db_result: Optional[Dict[str, Any]], lottery_type: str) -> bool:
        """
        判断是否应该从网络更新数据
        
        Args:
            db_result: 数据库中的最新结果
            lottery_type: 彩票类型
            
        Returns:
            bool: True表示应该从网络更新，False表示可以使用数据库数据
        """
        # 如果数据库没有数据，需要从网络获取
        if not db_result:
            return True
        
        # 检查数据新鲜度
        draw_date = db_result.get('draw_date')
        if not draw_date:
            return True
        
        # 如果数据不够新鲜，需要从网络更新
        if not self._is_data_fresh(draw_date, lottery_type):
            logger.info(f"{lottery_type}数据已过期，需要从网络更新")
            return True
        
        return False
    
    async def get_ssq_latest(self) -> Optional[LotteryResult]:
        """获取双色球最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_ssq()
            
            if self._should_update_from_network(db_result, "双色球"):
                logger.info("从网络获取双色球数据")
                data = await self._fetch_lottery_data('双色球')
                if data and data['result']:
                    result_data = data['result'][0]
                    
                    # 解析红球和蓝球
                    red_balls = result_data['red'].split(',')
                    blue_ball = result_data['blue']
                    
                    # 格式化奖池金额
                    pool_money = result_data.get('poolmoney', '')
                    if pool_money and pool_money.isdigit():
                        pool_money = f"{int(pool_money) / 100000000:.2f}亿元"
                    
                    # 格式化销售金额
                    sales = result_data.get('sales', '')
                    if sales and sales.isdigit():
                        sales = f"{int(sales) / 100000000:.2f}亿元"
                    
                    # 保存到数据库
                    self.db.save_ssq_result(
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        red_balls=red_balls,
                        blue_ball=blue_ball,
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
                    
                    # 更新号码统计
                    self.db.update_number_statistics('双色球', red_balls + [blue_ball])
                    
                    return LotteryResult(
                        lottery_type="双色球",
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=red_balls,
                        special_numbers=[blue_ball],
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
            else:
                logger.info("从本地数据库获取双色球数据")
                return LotteryResult(
                    lottery_type="双色球",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['red_balls'],
                    special_numbers=[db_result['blue_ball']],
                    prize_pool=db_result['prize_pool'],
                    sales_amount=db_result['sales_amount']
                )
        except Exception as e:
            logger.error(f"获取双色球数据失败: {e}")
            return None
    
    async def get_3d_latest(self) -> Optional[LotteryResult]:
        """获取福彩3D最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_3d()
            
            if self._should_update_from_network(db_result, "福彩3D"):
                logger.info("从网络获取福彩3D数据")
                data = await self._fetch_lottery_data('福彩3D')
                if data and data['result']:
                    result_data = data['result'][0]
                    
                    # 解析3D号码 (格式: "2,5,5")
                    numbers = result_data['red'].split(',')
                    
                    # 格式化销售金额
                    sales = result_data.get('sales', '')
                    if sales and sales.isdigit():
                        sales = f"{int(sales) / 10000:.1f}万元"
                    
                    # 保存到数据库
                    self.db.save_3d_result(
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=numbers,
                        sales_amount=sales
                    )
                    
                    # 更新号码统计
                    self.db.update_number_statistics('福彩3D', numbers)
                    
                    return LotteryResult(
                        lottery_type="福彩3D",
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=numbers,
                        sales_amount=sales
                    )
            else:
                logger.info("从本地数据库获取福彩3D数据")
                return LotteryResult(
                    lottery_type="福彩3D",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['numbers'],
                    sales_amount=db_result['sales_amount']
                )
        except Exception as e:
            logger.error(f"获取福彩3D数据失败: {e}")
            return None
    
    async def get_qlc_latest(self) -> Optional[LotteryResult]:
        """获取七乐彩最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_qlc()
            
            if self._should_update_from_network(db_result, "七乐彩"):
                logger.info("从网络获取七乐彩数据")
                data = await self._fetch_lottery_data('七乐彩')
                if data and data['result']:
                    result_data = data['result'][0]
                    
                    # 解析基本号码和特别号码
                    basic_numbers = result_data['red'].split(',')
                    special_number = result_data['blue']
                    
                    # 格式化奖池金额
                    pool_money = result_data.get('poolmoney', '0')
                    if pool_money and pool_money.isdigit():
                        if int(pool_money) == 0:
                            pool_money = "0元"
                        else:
                            pool_money = f"{int(pool_money) / 10000:.2f}万元"
                    
                    # 格式化销售金额
                    sales = result_data.get('sales', '')
                    if sales and sales.isdigit():
                        sales = f"{int(sales) / 10000:.1f}万元"
                    
                    # 保存到数据库
                    self.db.save_qlc_result(
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        basic_numbers=basic_numbers,
                        special_number=special_number,
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
                    
                    # 更新号码统计
                    self.db.update_number_statistics('七乐彩', basic_numbers + [special_number])
                    
                    return LotteryResult(
                        lottery_type="七乐彩",
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=basic_numbers,
                        special_numbers=[special_number],
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
            else:
                logger.info("从本地数据库获取七乐彩数据")
                return LotteryResult(
                    lottery_type="七乐彩",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['basic_numbers'],
                    special_numbers=[db_result['special_number']],
                    prize_pool=db_result['prize_pool'],
                    sales_amount=db_result['sales_amount']
                )
        except Exception as e:
            logger.error(f"获取七乐彩数据失败: {e}")
            return None
    
    async def get_kl8_latest(self) -> Optional[LotteryResult]:
        """获取快乐8最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_kl8()
            
            if self._should_update_from_network(db_result, "快乐8"):
                logger.info("从网络获取快乐8数据")
                data = await self._fetch_lottery_data('快乐8')
                if data and data['result']:
                    result_data = data['result'][0]
                    
                    # 解析快乐8号码 (20个号码)
                    numbers = result_data['red'].split(',')
                    
                    # 格式化奖池金额
                    pool_money = result_data.get('poolmoney', '')
                    if pool_money and pool_money.replace('.', '').isdigit():
                        pool_money = f"{float(pool_money) / 10000:.2f}万元"
                    
                    # 格式化销售金额
                    sales = result_data.get('sales', '')
                    if sales and sales.isdigit():
                        sales = f"{int(sales) / 10000:.1f}万元"
                    
                    # 保存到数据库
                    self.db.save_kl8_result(
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=numbers,
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
                    
                    # 更新号码统计
                    self.db.update_number_statistics('快乐8', numbers)
                    
                    return LotteryResult(
                        lottery_type="快乐8",
                        period=result_data['code'],
                        draw_date=result_data['date'],
                        numbers=numbers,
                        prize_pool=pool_money,
                        sales_amount=sales
                    )
            else:
                logger.info("从本地数据库获取快乐8数据")
                return LotteryResult(
                    lottery_type="快乐8",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['numbers'],
                    prize_pool=db_result['prize_pool'],
                    sales_amount=db_result['sales_amount']
                )
        except Exception as e:
            logger.error(f"获取快乐8数据失败: {e}")
            return None
    
    def _check_period_continuity(self, db_results: List[Dict[str, Any]], lottery_type: str) -> bool:
        """
        检查期号连续性 - 通过检查日期间隔来判断是否有缺失
        
        Args:
            db_results: 数据库查询结果（按期号降序排列）
            lottery_type: 彩票类型
            
        Returns:
            bool: True表示期号连续，False表示有缺失
        """
        if not db_results or len(db_results) < 2:
            return True  # 数据太少无法判断，认为连续
        
        try:
            # 解析日期并检查连续性
            dates = []
            for item in db_results:
                draw_date = item.get('draw_date', '')
                if not draw_date:
                    continue
                # 处理日期格式，移除星期信息
                clean_date = draw_date.split('(')[0] if '(' in draw_date else draw_date
                try:
                    date_obj = datetime.strptime(clean_date, "%Y-%m-%d")
                    dates.append(date_obj)
                except:
                    continue
            
            if len(dates) < 2:
                return True  # 日期数据不足，无法判断
            
            # 根据彩票类型确定合理的开奖间隔
            # 双色球：每周二、四、日（间隔1-3天）
            # 福彩3D：每天（间隔1天）
            # 七乐彩：每周一、三、五（间隔1-3天）
            # 快乐8：每天（间隔1天）
            max_days_gap = {
                "双色球": 4,  # 允许最多4天间隔（考虑节假日等）
                "福彩3D": 2,  # 每天开奖，允许最多2天间隔
                "七乐彩": 4,  # 允许最多4天间隔
                "快乐8": 2   # 每天开奖，允许最多2天间隔
            }.get(lottery_type, 3)
            
            # 检查日期间隔（降序排列，所以是前减后）
            for i in range(len(dates) - 1):
                days_gap = (dates[i] - dates[i + 1]).days
                if days_gap > max_days_gap:
                    logger.warning(f"{lottery_type}日期不连续：{dates[i].strftime('%Y-%m-%d')} 和 {dates[i+1].strftime('%Y-%m-%d')} 之间间隔{days_gap}天，超过允许的{max_days_gap}天")
                    return False
            
            return True
        except Exception as e:
            logger.warning(f"检查期号连续性失败: {e}")
            # 如果检查失败，保守起见认为不连续，需要更新
            return False
    
    async def get_historical_data(self, lottery_type: str, periods: int = 10) -> List[LotteryResult]:
        """获取历史开奖数据"""
        try:
            # 首先尝试从数据库获取
            db_results = self.db.get_historical_data(lottery_type, periods)
            
            # 检查是否需要从网络更新数据
            should_update = False
            
            if not db_results:
                # 数据库没有数据，需要从网络获取
                should_update = True
            elif len(db_results) < periods:
                # 数据库数据不足，需要从网络获取
                should_update = True
            else:
                # 检查最新数据的新鲜度
                latest_result = db_results[0]  # 最新的数据
                if not self._is_data_fresh(latest_result.get('draw_date', ''), lottery_type):
                    should_update = True
                # 检查期号连续性
                elif not self._check_period_continuity(db_results, lottery_type):
                    logger.warning(f"{lottery_type}数据库中期号不连续，需要从网络更新")
                    should_update = True
            
            if not should_update:
                logger.info(f"从本地数据库获取{lottery_type}历史数据")
                results = []
                for item in db_results:
                    if lottery_type == "双色球":
                        result = LotteryResult(
                            lottery_type="双色球",
                            period=item['period'],
                            draw_date=item['draw_date'],
                            numbers=item['red_balls'],
                            special_numbers=[item['blue_ball']],
                            prize_pool=item['prize_pool'],
                            sales_amount=item['sales_amount']
                        )
                    elif lottery_type == "福彩3D":
                        result = LotteryResult(
                            lottery_type="福彩3D",
                            period=item['period'],
                            draw_date=item['draw_date'],
                            numbers=item['numbers'],
                            sales_amount=item['sales_amount']
                        )
                    elif lottery_type == "七乐彩":
                        result = LotteryResult(
                            lottery_type="七乐彩",
                            period=item['period'],
                            draw_date=item['draw_date'],
                            numbers=item['basic_numbers'],
                            special_numbers=[item['special_number']],
                            prize_pool=item['prize_pool'],
                            sales_amount=item['sales_amount']
                        )
                    elif lottery_type == "快乐8":
                        result = LotteryResult(
                            lottery_type="快乐8",
                            period=item['period'],
                            draw_date=item['draw_date'],
                            numbers=item['numbers'],
                            prize_pool=item['prize_pool'],
                            sales_amount=item['sales_amount']
                        )
                    else:
                        continue
                    results.append(result)
                return results
            
            # 从网络获取并保存数据
            logger.info(f"从网络获取{lottery_type}历史数据")
            data = await self._fetch_lottery_data(lottery_type, periods)
            if not data or not data['result']:
                # 如果网络获取失败，尝试返回数据库中的可用数据
                if db_results:
                    logger.warning(f"网络获取{lottery_type}数据失败，返回数据库中的可用数据")
                    return self._convert_db_results_to_lottery_results(db_results, lottery_type)
                return []
            
            results = []
            for item in data['result']:
                if lottery_type == "双色球":
                    # 解析红球和蓝球
                    red_balls = item['red'].split(',')
                    blue_ball = item['blue']
                    
                    # 保存到数据库
                    self.db.save_ssq_result(
                        period=item['code'],
                        draw_date=item['date'],
                        red_balls=red_balls,
                        blue_ball=blue_ball
                    )
                    
                    result = LotteryResult(
                        lottery_type="双色球",
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=red_balls,
                        special_numbers=[blue_ball]
                    )
                    
                elif lottery_type == "福彩3D":
                    # 解析3D号码
                    numbers = item['red'].split(',')
                    
                    # 保存到数据库
                    self.db.save_3d_result(
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=numbers
                    )
                    
                    result = LotteryResult(
                        lottery_type="福彩3D",
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=numbers
                    )
                    
                elif lottery_type == "七乐彩":
                    # 解析基本号码和特别号码
                    basic_numbers = item['red'].split(',')
                    special_number = item['blue']
                    
                    # 保存到数据库
                    self.db.save_qlc_result(
                        period=item['code'],
                        draw_date=item['date'],
                        basic_numbers=basic_numbers,
                        special_number=special_number
                    )
                    
                    result = LotteryResult(
                        lottery_type="七乐彩",
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=basic_numbers,
                        special_numbers=[special_number]
                    )
                    
                elif lottery_type == "快乐8":
                    # 解析快乐8号码
                    numbers = item['red'].split(',')
                    
                    # 保存到数据库
                    self.db.save_kl8_result(
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=numbers
                    )
                    
                    result = LotteryResult(
                        lottery_type="快乐8",
                        period=item['code'],
                        draw_date=item['date'],
                        numbers=numbers
                    )
                    
                else:
                    continue
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"获取{lottery_type}历史数据失败: {e}")
            # 如果出错，尝试返回数据库中的可用数据
            try:
                db_results = self.db.get_historical_data(lottery_type, periods)
                if db_results:
                    logger.warning(f"返回数据库中的{lottery_type}数据作为备选")
                    return self._convert_db_results_to_lottery_results(db_results, lottery_type)
            except:
                pass
            return []
    
    def _convert_db_results_to_lottery_results(self, db_results: List[Dict[str, Any]], lottery_type: str) -> List[LotteryResult]:
        """将数据库结果转换为LotteryResult对象列表"""
        results = []
        for item in db_results:
            try:
                if lottery_type == "双色球":
                    result = LotteryResult(
                        lottery_type="双色球",
                        period=item['period'],
                        draw_date=item['draw_date'],
                        numbers=item['red_balls'],
                        special_numbers=[item['blue_ball']],
                        prize_pool=item.get('prize_pool'),
                        sales_amount=item.get('sales_amount')
                    )
                elif lottery_type == "福彩3D":
                    result = LotteryResult(
                        lottery_type="福彩3D",
                        period=item['period'],
                        draw_date=item['draw_date'],
                        numbers=item['numbers'],
                        sales_amount=item.get('sales_amount')
                    )
                elif lottery_type == "七乐彩":
                    result = LotteryResult(
                        lottery_type="七乐彩",
                        period=item['period'],
                        draw_date=item['draw_date'],
                        numbers=item['basic_numbers'],
                        special_numbers=[item['special_number']],
                        prize_pool=item.get('prize_pool'),
                        sales_amount=item.get('sales_amount')
                    )
                elif lottery_type == "快乐8":
                    result = LotteryResult(
                        lottery_type="快乐8",
                        period=item['period'],
                        draw_date=item['draw_date'],
                        numbers=item['numbers'],
                        prize_pool=item.get('prize_pool'),
                        sales_amount=item.get('sales_amount')
                    )
                else:
                    continue
                results.append(result)
            except Exception as e:
                logger.warning(f"转换数据库结果失败: {e}")
                continue
        return results
    
    async def force_sync_data(self, lottery_type: str, periods: int = 20) -> Dict[str, Any]:
        """
        强制同步指定彩票类型的数据
        
        Args:
            lottery_type: 彩票类型
            periods: 同步的期数
            
        Returns:
            Dict: 同步结果信息
        """
        try:
            logger.info(f"开始强制同步{lottery_type}数据，期数: {periods}")
            
            # 从网络获取最新数据
            data = await self._fetch_lottery_data(lottery_type, periods)
            if not data or not data['result']:
                return {
                    "success": False,
                    "message": f"网络获取{lottery_type}数据失败",
                    "lottery_type": lottery_type,
                    "periods": periods
                }
            
            # 统计同步的数据
            synced_count = 0
            for item in data['result']:
                try:
                    if lottery_type == "双色球":
                        red_balls = item['red'].split(',')
                        blue_ball = item['blue']
                        
                        # 格式化奖池金额
                        pool_money = item.get('poolmoney', '')
                        if pool_money and pool_money.isdigit():
                            pool_money = f"{int(pool_money) / 100000000:.2f}亿元"
                        
                        # 格式化销售金额
                        sales = item.get('sales', '')
                        if sales and sales.isdigit():
                            sales = f"{int(sales) / 100000000:.2f}亿元"
                        
                        # 保存到数据库
                        if self.db.save_ssq_result(
                            period=item['code'],
                            draw_date=item['date'],
                            red_balls=red_balls,
                            blue_ball=blue_ball,
                            prize_pool=pool_money,
                            sales_amount=sales
                        ):
                            synced_count += 1
                            # 更新号码统计
                            self.db.update_number_statistics('双色球', red_balls + [blue_ball])
                    
                    elif lottery_type == "福彩3D":
                        numbers = item['red'].split(',')
                        
                        # 格式化销售金额
                        sales = item.get('sales', '')
                        if sales and sales.isdigit():
                            sales = f"{int(sales) / 10000:.1f}万元"
                        
                        # 保存到数据库
                        if self.db.save_3d_result(
                            period=item['code'],
                            draw_date=item['date'],
                            numbers=numbers,
                            sales_amount=sales
                        ):
                            synced_count += 1
                            # 更新号码统计
                            self.db.update_number_statistics('福彩3D', numbers)
                    
                    elif lottery_type == "七乐彩":
                        basic_numbers = item['red'].split(',')
                        special_number = item['blue']
                        
                        # 格式化奖池金额
                        pool_money = item.get('poolmoney', '0')
                        if pool_money and pool_money.isdigit():
                            if int(pool_money) == 0:
                                pool_money = "0元"
                            else:
                                pool_money = f"{int(pool_money) / 10000:.2f}万元"
                        
                        # 格式化销售金额
                        sales = item.get('sales', '')
                        if sales and sales.isdigit():
                            sales = f"{int(sales) / 10000:.1f}万元"
                        
                        # 保存到数据库
                        if self.db.save_qlc_result(
                            period=item['code'],
                            draw_date=item['date'],
                            basic_numbers=basic_numbers,
                            special_number=special_number,
                            prize_pool=pool_money,
                            sales_amount=sales
                        ):
                            synced_count += 1
                            # 更新号码统计
                            self.db.update_number_statistics('七乐彩', basic_numbers + [special_number])
                    
                    elif lottery_type == "快乐8":
                        numbers = item['red'].split(',')
                        
                        # 格式化奖池金额
                        pool_money = item.get('poolmoney', '')
                        if pool_money and pool_money.replace('.', '').isdigit():
                            pool_money = f"{float(pool_money) / 10000:.2f}万元"
                        
                        # 格式化销售金额
                        sales = item.get('sales', '')
                        if sales and sales.isdigit():
                            sales = f"{int(sales) / 10000:.1f}万元"
                        
                        # 保存到数据库
                        if self.db.save_kl8_result(
                            period=item['code'],
                            draw_date=item['date'],
                            numbers=numbers,
                            prize_pool=pool_money,
                            sales_amount=sales
                        ):
                            synced_count += 1
                            # 更新号码统计
                            self.db.update_number_statistics('快乐8', numbers)
                
                except Exception as e:
                    logger.warning(f"保存{item['code']}期数据失败: {e}")
                    continue
            
            logger.info(f"{lottery_type}数据同步完成，成功同步{synced_count}期")
            return {
                "success": True,
                "message": f"{lottery_type}数据同步成功",
                "lottery_type": lottery_type,
                "periods": periods,
                "synced_count": synced_count,
                "total_available": len(data['result'])
            }
            
        except Exception as e:
            logger.error(f"强制同步{lottery_type}数据失败: {e}")
            return {
                "success": False,
                "message": f"同步失败: {str(e)}",
                "lottery_type": lottery_type,
                "periods": periods
            }
    
    def analyze_numbers(self, results: List[LotteryResult]) -> LotteryAnalysis:
        """分析号码统计 - 基于传入的results进行统计，不使用数据库累积统计"""
        logger.info(f"基于{len(results)}期数据计算号码统计")
        
        # 直接从传入的results计算频率统计
        frequency = {}
        all_numbers = []
        
        for result in results:
            all_numbers.extend(result.numbers)
            if result.special_numbers:
                all_numbers.extend(result.special_numbers)
        
        # 统计频率
        for num in all_numbers:
            frequency[num] = frequency.get(num, 0) + 1
        
        # 排序找出热号和冷号
        sorted_nums = sorted(frequency.items(), key=lambda x: x[1], reverse=True)
        hot_numbers = [num for num, _ in sorted_nums[:10]]
        cold_numbers = [num for num, _ in sorted_nums[-10:]]
        
        return LotteryAnalysis(
            hot_numbers=hot_numbers,
            cold_numbers=cold_numbers,
            frequency_stats=frequency,
            consecutive_analysis={
                "total_periods": len(results),
                "most_frequent": sorted_nums[0] if sorted_nums else ("", 0),
                "least_frequent": sorted_nums[-1] if sorted_nums else ("", 0)
            }
        )
    
    async def analyze_seq_numbers(
        self,
        lottery_type: str,
        periods: int,
        sequence_length: int,
    ) -> Dict[str, Any]:
        """
        分析号码连续出现概率（滑窗）
        
        Args:
            lottery_type: 彩票类型（需在 lottery_codes 中）
            periods: 使用的期数窗口
            sequence_length: 连续出现期数
        Returns:
            dict: 理论值、实测值、计数等
        """
        if sequence_length < 1:
            raise ValueError("sequence_length must be >= 1")
        # 获取历史数据
        results = await self.get_historical_data(lottery_type, periods)
        if not results:
            raise ValueError("未获取到历史数据")
        num_draws = len(results)
        if sequence_length > num_draws:
            raise ValueError("sequence_length 大于可用期数")
        
        # 抽取号码（仅主号码）
        rows: List[List[int]] = []
        for r in results:
            try:
                rows.append([int(n) for n in r.numbers])
            except Exception:
                # 如果存在非数字，直接跳过该期
                continue
        if not rows:
            raise ValueError("历史数据格式异常，缺少号码")
        
        numbers_per_draw = len(rows[0])
        # 不同彩票的号码池大小
        pool_sizes = {
            "双色球": 33,
            "福彩3D": 10,
            "七乐彩": 30,
            "快乐8": 80,
        }
        pool_size = pool_sizes.get(lottery_type)
        if not pool_size:
            raise ValueError(f"不支持的彩票类型: {lottery_type}")
        if numbers_per_draw > pool_size:
            raise ValueError("每期号码数量大于号码池大小，数据异常")
        
        # 理论：单号在一期开出的概率
        p_single = numbers_per_draw / pool_size
        theoretical = p_single ** sequence_length
        
        # 实测：滑窗计数
        from collections import Counter
        balls = range(1, pool_size + 1)
        total_windows = (num_draws - sequence_length + 1) * pool_size
        hit_count = 0
        max_run = {}
        
        for b in balls:
            # 滑窗连续
            for i in range(num_draws - sequence_length + 1):
                if all(b in rows[i + j] for j in range(sequence_length)):
                    hit_count += 1
            # 最长连出
            cur = longest = 0
            for reds in rows:
                if b in reds:
                    cur += 1
                    longest = max(longest, cur)
                else:
                    cur = 0
            max_run[b] = longest
        
        empirical = hit_count / total_windows if total_windows else 0
        max_run_dist = Counter(max_run.values())
        
        return {
            "lottery_type": lottery_type,
            "periods_used": num_draws,
            "sequence_length": sequence_length,
            "pool_size": pool_size,
            "numbers_per_draw": numbers_per_draw,
            "theoretical_prob": theoretical,
            "empirical_prob": empirical,
            "counts": {
                "hits": hit_count,
                "windows": total_windows,
            },
            "max_run_distribution": dict(sorted(max_run_dist.items())),
        }
    
    def generate_random_numbers(self, lottery_type: str) -> Dict[str, Any]:
        """生成随机号码推荐"""
        import random
        
        if lottery_type == "双色球":
            red_balls = sorted(random.sample(range(1, 34), 6))
            blue_ball = random.randint(1, 16)
            return {
                "lottery_type": "双色球",
                "red_balls": [f"{num:02d}" for num in red_balls],
                "blue_ball": f"{blue_ball:02d}",
                "format": "红球: " + " ".join([f"{num:02d}" for num in red_balls]) + f" 蓝球: {blue_ball:02d}"
            }
        elif lottery_type == "福彩3D":
            numbers = [random.randint(0, 9) for _ in range(3)]
            return {
                "lottery_type": "福彩3D",
                "numbers": [str(num) for num in numbers],
                "format": " ".join([str(num) for num in numbers])
            }
        elif lottery_type == "七乐彩":
            basic_balls = sorted(random.sample(range(1, 31), 7))
            special_ball = random.choice([num for num in range(1, 31) if num not in basic_balls])
            return {
                "lottery_type": "七乐彩",
                "basic_balls": [f"{num:02d}" for num in basic_balls],
                "special_ball": f"{special_ball:02d}",
                "format": "基本球: " + " ".join([f"{num:02d}" for num in basic_balls]) + f" 特别号: {special_ball:02d}"
            }
        else:  # 快乐8
            numbers = sorted(random.sample(range(1, 81), 20))
            return {
                "lottery_type": "快乐8",
                "numbers": [f"{num:02d}" for num in numbers],
                "format": "号码: " + " ".join([f"{num:02d}" for num in numbers])
            }

# MCP Server实现
def create_swlc_server() -> Server:
    """创建SWLC MCP服务器"""
    server = Server("swlc-mcp")
    lottery_service = SWLCService()
    
    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        """列出所有可用工具"""
        return [
            types.Tool(
                name="get_latest_ssq",
                description="获取双色球最新开奖结果",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="get_latest_3d",
                description="获取福彩3D最新开奖结果",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="get_latest_qlc", 
                description="获取七乐彩最新开奖结果",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="get_latest_kl8",
                description="获取快乐8最新开奖结果",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="get_historical_data",
                description="获取指定彩票类型的历史开奖数据",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 10,
                            "description": "获取期数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="analyze_numbers",
                description="分析彩票号码统计信息，包括热号、冷号等",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string", 
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1000,
                            "default": 30,
                            "description": "分析期数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="analyze_seq_numbers",
                description="分析号码连续出现概率（滑窗），返回理论值与实测值",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 5,
                            "maximum": 1000,
                            "default": 100,
                            "description": "分析期数"
                        },
                        "sequence_length": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 2,
                            "description": "连续期数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="generate_random_numbers",
                description="生成随机彩票号码推荐",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 1,
                            "description": "生成组数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="sync_lottery_data",
                description="同步指定彩票类型的最新数据到本地数据库",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                            "description": "同步期数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="force_sync_data",
                description="强制同步指定彩票类型的最新数据到本地数据库",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "periods": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 1000,
                            "default": 20,
                            "description": "同步期数"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="get_database_info",
                description="获取本地数据库统计信息",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            types.Tool(
                name="predict_lottery",
                description="预测彩票号码，基于历史数据生成预测结果",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "method": {
                            "type": "string",
                            "enum": ["rule"],
                            "default": "rule",
                            "description": "预测方法"
                        },
                        "count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 5,
                            "description": "预测组数"
                        },
                        "strategy": {
                            "type": "string",
                            "enum": ["all", "balanced", "cold_recovery", "hot_focus", "interval_balance", "contrarian"],
                            "default": "all",
                            "description": "预测策略"
                        }
                    },
                    "required": ["lottery_type"]
                }
            ),
            types.Tool(
                name="backtest_lottery",
                description="回测预测算法，评估预测准确性",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "lottery_type": {
                            "type": "string",
                            "enum": ["双色球", "福彩3D", "七乐彩", "快乐8"],
                            "description": "彩票类型"
                        },
                        "window_size": {
                            "type": "integer",
                            "minimum": 50,
                            "maximum": 500,
                            "default": 100,
                            "description": "窗口大小（训练数据期数）"
                        },
                        "step": {
                            "type": "integer",
                            "minimum": 10,
                            "maximum": 100,
                            "default": 50,
                            "description": "步长（每次移动的期数）"
                        }
                    },
                    "required": ["lottery_type"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        """调用工具"""
        try:
            if name == "get_latest_ssq":
                result = await lottery_service.get_ssq_latest()
                if result:
                    return [types.TextContent(
                        type="text",
                        text=f"""双色球最新开奖结果：
期号：{result.period}
开奖日期：{result.draw_date}
开奖号码：{' '.join(result.numbers)} + {' '.join(result.special_numbers or [])}
奖池金额：{result.prize_pool or '暂无'}
销售金额：{result.sales_amount or '暂无'}"""
                    )]
                else:
                    return [types.TextContent(type="text", text="获取双色球数据失败")]
            
            elif name == "get_latest_3d":
                result = await lottery_service.get_3d_latest()
                if result:
                    return [types.TextContent(
                        type="text",
                        text=f"""福彩3D最新开奖结果：
期号：{result.period}
开奖日期：{result.draw_date}
开奖号码：{' '.join(result.numbers)}
奖池金额：{result.prize_pool or '暂无'}"""
                    )]
                else:
                    return [types.TextContent(type="text", text="获取福彩3D数据失败")]
            
            elif name == "get_latest_qlc":
                result = await lottery_service.get_qlc_latest()
                if result:
                    return [types.TextContent(
                        type="text", 
                        text=f"""七乐彩最新开奖结果：
期号：{result.period}
开奖日期：{result.draw_date}
基本号码：{' '.join(result.numbers)}
特别号码：{' '.join(result.special_numbers or [])}
奖池金额：{result.prize_pool or '暂无'}"""
                    )]
                else:
                    return [types.TextContent(type="text", text="获取七乐彩数据失败")]
            
            elif name == "get_latest_kl8":
                result = await lottery_service.get_kl8_latest()
                if result:
                    return [types.TextContent(
                        type="text",
                        text=f"""快乐8最新开奖结果：
期号：{result.period}
开奖日期：{result.draw_date}
开奖号码：{' '.join(result.numbers)}
奖池金额：{result.prize_pool or '暂无'}
销售金额：{result.sales_amount or '暂无'}"""
                    )]
                else:
                    return [types.TextContent(type="text", text="获取快乐8数据失败")]
            
            elif name == "get_historical_data":
                lottery_type = arguments.get("lottery_type")
                periods = arguments.get("periods", 10)
                
                results = await lottery_service.get_historical_data(lottery_type, periods)
                if results:
                    text_lines = [f"{lottery_type}历史开奖数据（最近{len(results)}期）：\n"]
                    
                    for result in results:
                        if result.special_numbers:
                            numbers_str = f"{' '.join(result.numbers)} + {' '.join(result.special_numbers)}"
                        else:
                            numbers_str = ' '.join(result.numbers)
                        
                        text_lines.append(f"期号：{result.period} 日期：{result.draw_date} 号码：{numbers_str}")
                    
                    return [types.TextContent(type="text", text="\n".join(text_lines))]
                else:
                    return [types.TextContent(type="text", text="获取历史数据失败")]
            
            elif name == "analyze_numbers":
                lottery_type = arguments.get("lottery_type")
                periods = arguments.get("periods", 30)
                
                results = await lottery_service.get_historical_data(lottery_type, periods)
                if results:
                    analysis = lottery_service.analyze_numbers(results)
                    
                    text = f"""{lottery_type}号码分析（最近{periods}期）：

热门号码（前10）：{' '.join(analysis.hot_numbers)}
冷门号码（后10）：{' '.join(analysis.cold_numbers)}

统计信息：
- 分析期数：{analysis.consecutive_analysis['total_periods']}期
- 最高频号码：{analysis.consecutive_analysis['most_frequent'][0]} （出现{analysis.consecutive_analysis['most_frequent'][1]}次）
- 最低频号码：{analysis.consecutive_analysis['least_frequent'][0]} （出现{analysis.consecutive_analysis['least_frequent'][1]}次）

详细频率统计："""
                    
                    # 添加详细频率信息
                    sorted_freq = sorted(analysis.frequency_stats.items(), key=lambda x: x[1], reverse=True)
                    for num, freq in sorted_freq[:15]:  # 显示前15个
                        text += f"\n号码 {num}: {freq}次"
                    
                    return [types.TextContent(type="text", text=text)]
                else:
                    return [types.TextContent(type="text", text="获取数据失败，无法进行分析")]
            
            elif name == "analyze_seq_numbers":
                lottery_type = arguments.get("lottery_type")
                periods = arguments.get("periods", 100)
                sequence_length = arguments.get("sequence_length", 2)
                
                result = await lottery_service.analyze_seq_numbers(
                    lottery_type=lottery_type,
                    periods=periods,
                    sequence_length=sequence_length,
                )
                
                detail = result.get("counts", {})
                text = (
                    f"{lottery_type} 连续出现分析（最近{result['periods_used']}期，连续{sequence_length}期）：\n\n"
                    f"- 理论概率: {result['theoretical_prob']:.8f}\n"
                    f"- 实测概率: {result['empirical_prob']:.8f}\n"
                    f"- 计数: {detail.get('hits', 0)} / {detail.get('windows', 0)}\n"
                    f"- 号码池: {result['pool_size']}，每期开出: {result['numbers_per_draw']}\n"
                    f"- 最长连出分布: {result.get('max_run_distribution', {})}"
                )
                return [types.TextContent(type="text", text=text)]
            
            elif name == "generate_random_numbers":
                lottery_type = arguments.get("lottery_type")
                count = arguments.get("count", 1)
                
                results = []
                for i in range(count):
                    random_result = lottery_service.generate_random_numbers(lottery_type)
                    results.append(f"推荐 {i+1}: {random_result['format']}")
                
                return [types.TextContent(
                    type="text",
                    text=f"{lottery_type}随机号码推荐：\n\n" + "\n".join(results)
                )]
            
            elif name == "sync_lottery_data":
                lottery_type = arguments.get("lottery_type")
                periods = arguments.get("periods", 10)
                
                try:
                    # 从网络获取数据并保存到数据库
                    results = await lottery_service.get_historical_data(lottery_type, periods)
                    if results:
                        # 记录同步日志
                        lottery_service.db.log_sync(lottery_type, len(results))
                        return [types.TextContent(
                            type="text",
                            text=f"成功同步{lottery_type}数据{len(results)}期到本地数据库"
                        )]
                    else:
                        lottery_service.db.log_sync(lottery_type, 0, 'failed', '获取数据失败')
                        return [types.TextContent(type="text", text=f"同步{lottery_type}数据失败")]
                except Exception as e:
                    lottery_service.db.log_sync(lottery_type, 0, 'failed', str(e))
                    return [types.TextContent(type="text", text=f"同步{lottery_type}数据失败：{str(e)}")]
            
            elif name == "force_sync_data":
                lottery_type = arguments.get("lottery_type")
                periods = arguments.get("periods", 20)
                
                try:
                    sync_result = await lottery_service.force_sync_data(lottery_type, periods)
                    if sync_result["success"]:
                        return [types.TextContent(
                            type="text",
                            text=f"成功强制同步{sync_result['lottery_type']}数据{sync_result['synced_count']}期到本地数据库"
                        )]
                    else:
                        return [types.TextContent(
                            type="text",
                            text=f"强制同步{sync_result['lottery_type']}数据失败: {sync_result['message']}"
                        )]
                except Exception as e:
                    return [types.TextContent(type="text", text=f"强制同步{lottery_type}数据失败：{str(e)}")]
            
            elif name == "get_database_info":
                try:
                    info = lottery_service.db.get_database_info()
                    text_lines = ["本地数据库统计信息：\n"]
                    
                    # 各表记录数
                    text_lines.append("各彩票类型记录数：")
                    for table, count in info.items():
                        if table != 'last_sync':
                            lottery_name = {
                                'ssq_results': '双色球',
                                'fucai3d_results': '福彩3D', 
                                'qilecai_results': '七乐彩',
                                'kuaile8_results': '快乐8'
                            }.get(table, table)
                            text_lines.append(f"- {lottery_name}: {count}期")
                    
                    # 最新同步时间
                    if 'last_sync' in info and info['last_sync']:
                        text_lines.append("\n最新同步时间：")
                        for lottery_type, sync_time in info['last_sync'].items():
                            text_lines.append(f"- {lottery_type}: {sync_time}")
                    
                    return [types.TextContent(type="text", text="\n".join(text_lines))]
                except Exception as e:
                    return [types.TextContent(type="text", text=f"获取数据库信息失败：{str(e)}")]
            
            elif name == "predict_lottery":
                lottery_type = arguments.get("lottery_type")
                method = arguments.get("method", "rule")
                count = arguments.get("count", 5)
                strategy = arguments.get("strategy", "all")
                
                try:
                    # 获取历史数据用于预测
                    historical_data = await lottery_service.get_historical_data(lottery_type, 120)
                    if not historical_data:
                        return [types.TextContent(type="text", text=f"获取{lottery_type}历史数据失败，无法进行预测")]
                    
                    # 转换为字典格式
                    history_dict = [{
                        'period': r.period,
                        'numbers': r.numbers,
                        'special_numbers': r.special_numbers,
                        'draw_date': r.draw_date
                    } for r in historical_data]
                    
                    # 执行预测
                    predictions = await lottery_service.prediction_manager.predict(
                        lottery_type, history_dict, method=method, count=count, strategy=strategy
                    )
                    
                    if predictions:
                        text_lines = [f"{lottery_type}预测结果（方法：{method}，策略：{strategy}）：\n"]
                        for i, pred in enumerate(predictions, 1):
                            if pred.special_numbers:
                                numbers_str = f"{' '.join(pred.numbers)} + {' '.join(pred.special_numbers)}"
                            else:
                                numbers_str = ' '.join(pred.numbers)
                            text_lines.append(f"预测 {i}: {numbers_str} (置信度: {pred.confidence:.2%})")
                        
                        return [types.TextContent(type="text", text="\n".join(text_lines))]
                    else:
                        return [types.TextContent(type="text", text=f"{lottery_type}预测失败")]
                        
                except Exception as e:
                    logger.error(f"预测失败: {e}")
                    return [types.TextContent(type="text", text=f"预测失败：{str(e)}")]
            
            elif name == "backtest_lottery":
                lottery_type = arguments.get("lottery_type")
                window_size = arguments.get("window_size", 100)
                step = arguments.get("step", 50)
                
                try:
                    # 获取历史数据用于回测
                    historical_data = await lottery_service.get_historical_data(lottery_type, window_size * 2)
                    if len(historical_data) < window_size:
                        return [types.TextContent(type="text", text=f"历史数据不足，需要至少{window_size}期数据")]
                    
                    # 转换为字典格式
                    history_dict = [{
                        'period': r.period,
                        'numbers': r.numbers,
                        'special_numbers': r.special_numbers,
                        'draw_date': r.draw_date
                    } for r in historical_data]
                    
                    # 执行回测
                    backtest_result = await lottery_service.backtest_engine.run_backtest(
                        lottery_type, history_dict, window_size=window_size, step=step
                    )
                    
                    text_lines = [
                        f"{lottery_type}回测结果：\n",
                        f"总回测期数：{backtest_result.total_periods}期",
                        f"平均准确率：{backtest_result.average_accuracy:.2%}",
                        f"最佳策略：{backtest_result.best_strategy}",
                        "\n各策略表现："
                    ]
                    
                    for strategy, performance in backtest_result.strategy_performance.items():
                        text_lines.append(f"- {strategy}: 准确率 {performance:.2%}")
                    
                    return [types.TextContent(type="text", text="\n".join(text_lines))]
                    
                except Exception as e:
                    logger.error(f"回测失败: {e}")
                    return [types.TextContent(type="text", text=f"回测失败：{str(e)}")]
            
            else:
                return [types.TextContent(type="text", text=f"未知工具：{name}")]
        
        except Exception as e:
            logger.error(f"调用工具 {name} 失败: {e}")
            return [types.TextContent(type="text", text=f"工具调用失败：{str(e)}")]
    
    return server

async def async_main():
    """异步主函数"""
    server = create_swlc_server()
    
    # 通过stdio运行服务器
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

def main():
    """同步主函数入口点"""
    asyncio.run(async_main())

if __name__ == "__main__":
    main()