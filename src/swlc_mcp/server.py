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
    
    async def get_ssq_latest(self) -> Optional[LotteryResult]:
        """获取双色球最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_ssq()
            if db_result:
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
            
            # 如果数据库没有数据，从网络获取并保存
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
        except Exception as e:
            logger.error(f"获取双色球数据失败: {e}")
            return None
    
    async def get_3d_latest(self) -> Optional[LotteryResult]:
        """获取福彩3D最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_3d()
            if db_result:
                logger.info("从本地数据库获取福彩3D数据")
                return LotteryResult(
                    lottery_type="福彩3D",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['numbers'],
                    sales_amount=db_result['sales_amount']
                )
            
            # 如果数据库没有数据，从网络获取并保存
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
        except Exception as e:
            logger.error(f"获取福彩3D数据失败: {e}")
            return None
    
    async def get_qlc_latest(self) -> Optional[LotteryResult]:
        """获取七乐彩最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_qlc()
            if db_result:
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
            
            # 如果数据库没有数据，从网络获取并保存
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
        except Exception as e:
            logger.error(f"获取七乐彩数据失败: {e}")
            return None
    
    async def get_kl8_latest(self) -> Optional[LotteryResult]:
        """获取快乐8最新开奖结果"""
        try:
            # 首先尝试从数据库获取
            db_result = self.db.get_latest_kl8()
            if db_result:
                logger.info("从本地数据库获取快乐8数据")
                return LotteryResult(
                    lottery_type="快乐8",
                    period=db_result['period'],
                    draw_date=db_result['draw_date'],
                    numbers=db_result['numbers'],
                    prize_pool=db_result['prize_pool'],
                    sales_amount=db_result['sales_amount']
                )
            
            # 如果数据库没有数据，从网络获取并保存
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
        except Exception as e:
            logger.error(f"获取快乐8数据失败: {e}")
            return None
    
    async def get_historical_data(self, lottery_type: str, periods: int = 10) -> List[LotteryResult]:
        """获取历史开奖数据"""
        try:
            # 首先尝试从数据库获取
            db_results = self.db.get_historical_data(lottery_type, periods)
            if db_results:
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
            
            # 如果数据库数据不足，从网络获取并保存
            logger.info(f"从网络获取{lottery_type}历史数据")
            data = await self._fetch_lottery_data(lottery_type, periods)
            if not data or not data['result']:
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
                    # 解析快乐8号码 (20个号码)
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
            logger.error(f"获取历史数据失败: {e}")
            return []
    
    def analyze_numbers(self, results: List[LotteryResult]) -> LotteryAnalysis:
        """分析号码统计"""
        # 首先尝试从数据库获取统计信息
        if results:
            lottery_type = results[0].lottery_type
            db_stats = self.db.get_number_statistics(lottery_type)
            if db_stats:
                logger.info(f"从本地数据库获取{lottery_type}号码统计")
                # 排序找出热号和冷号
                sorted_nums = sorted(db_stats.items(), key=lambda x: x[1], reverse=True)
                hot_numbers = [num for num, _ in sorted_nums[:10]]
                cold_numbers = [num for num, _ in sorted_nums[-10:]]
                
                return LotteryAnalysis(
                    hot_numbers=hot_numbers,
                    cold_numbers=cold_numbers,
                    frequency_stats=db_stats,
                    consecutive_analysis={
                        "total_periods": len(results),
                        "most_frequent": sorted_nums[0] if sorted_nums else ("", 0),
                        "least_frequent": sorted_nums[-1] if sorted_nums else ("", 0)
                    }
                )
        
        # 如果数据库没有统计信息，从结果中计算
        logger.info("从结果数据计算号码统计")
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
                            "maximum": 500,
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
                            "maximum": 500,
                            "default": 30,
                            "description": "分析期数"
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
                name="get_database_info",
                description="获取本地数据库统计信息",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
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