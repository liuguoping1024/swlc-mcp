"""
彩票数据本地存储模块
使用SQLite数据库存储彩票开奖数据，减少网络查询
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class LotteryRecord:
    """彩票记录数据类"""
    lottery_type: str
    period: str
    draw_date: str
    numbers: str  # JSON格式存储
    special_numbers: Optional[str] = None  # JSON格式存储
    prize_pool: Optional[str] = None
    sales_amount: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class LotteryDatabase:
    """彩票数据库管理类"""
    
    def __init__(self, db_path: str = "lottery_data.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库和表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建彩票类型表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS lottery_types (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        type_name TEXT UNIQUE NOT NULL,
                        type_code TEXT UNIQUE NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建双色球表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ssq_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period TEXT UNIQUE NOT NULL,
                        draw_date TEXT NOT NULL,
                        red_balls TEXT NOT NULL,  -- JSON格式: ["01","02","03","04","05","06"]
                        blue_ball TEXT NOT NULL,
                        prize_pool TEXT,
                        sales_amount TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建福彩3D表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fucai3d_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period TEXT UNIQUE NOT NULL,
                        draw_date TEXT NOT NULL,
                        numbers TEXT NOT NULL,  -- JSON格式: ["2","5","5"]
                        sales_amount TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建七乐彩表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS qilecai_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period TEXT UNIQUE NOT NULL,
                        draw_date TEXT NOT NULL,
                        basic_numbers TEXT NOT NULL,  -- JSON格式: ["01","02","03","04","05","06","07"]
                        special_number TEXT NOT NULL,
                        prize_pool TEXT,
                        sales_amount TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建快乐8表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS kuaile8_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period TEXT UNIQUE NOT NULL,
                        draw_date TEXT NOT NULL,
                        numbers TEXT NOT NULL,  -- JSON格式: ["01","02","03",...,"20"]
                        prize_pool TEXT,
                        sales_amount TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建号码统计表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS number_statistics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lottery_type TEXT NOT NULL,
                        number TEXT NOT NULL,
                        frequency INTEGER DEFAULT 0,
                        last_appearance TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(lottery_type, number)
                    )
                """)
                
                # 创建数据同步记录表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sync_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        lottery_type TEXT NOT NULL,
                        sync_date TEXT NOT NULL,
                        records_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'success',
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 插入彩票类型数据
                lottery_types = [
                    ('双色球', 'ssq', '红球33选6+蓝球16选1'),
                    ('福彩3D', '3d', '3位数字，每位0-9'),
                    ('七乐彩', 'qlc', '30选7+特别号'),
                    ('快乐8', 'kl8', '80选20')
                ]
                
                cursor.executemany("""
                    INSERT OR IGNORE INTO lottery_types (type_name, type_code, description)
                    VALUES (?, ?, ?)
                """, lottery_types)
                
                conn.commit()
                logger.info("数据库初始化完成")
                
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
    
    def save_ssq_result(self, period: str, draw_date: str, red_balls: List[str], 
                       blue_ball: str, prize_pool: Optional[str] = None, 
                       sales_amount: Optional[str] = None) -> bool:
        """保存双色球开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO ssq_results 
                    (period, draw_date, red_balls, blue_ball, prize_pool, sales_amount, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    period, draw_date, json.dumps(red_balls), blue_ball,
                    prize_pool, sales_amount, datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"保存双色球数据成功: {period}")
                return True
                
        except Exception as e:
            logger.error(f"保存双色球数据失败: {e}")
            return False
    
    def save_3d_result(self, period: str, draw_date: str, numbers: List[str],
                      sales_amount: Optional[str] = None) -> bool:
        """保存福彩3D开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO fucai3d_results 
                    (period, draw_date, numbers, sales_amount, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    period, draw_date, json.dumps(numbers),
                    sales_amount, datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"保存福彩3D数据成功: {period}")
                return True
                
        except Exception as e:
            logger.error(f"保存福彩3D数据失败: {e}")
            return False
    
    def save_qlc_result(self, period: str, draw_date: str, basic_numbers: List[str],
                       special_number: str, prize_pool: Optional[str] = None,
                       sales_amount: Optional[str] = None) -> bool:
        """保存七乐彩开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO qilecai_results 
                    (period, draw_date, basic_numbers, special_number, prize_pool, sales_amount, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    period, draw_date, json.dumps(basic_numbers), special_number,
                    prize_pool, sales_amount, datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"保存七乐彩数据成功: {period}")
                return True
                
        except Exception as e:
            logger.error(f"保存七乐彩数据失败: {e}")
            return False
    
    def save_kl8_result(self, period: str, draw_date: str, numbers: List[str],
                       prize_pool: Optional[str] = None, sales_amount: Optional[str] = None) -> bool:
        """保存快乐8开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO kuaile8_results 
                    (period, draw_date, numbers, prize_pool, sales_amount, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    period, draw_date, json.dumps(numbers),
                    prize_pool, sales_amount, datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.info(f"保存快乐8数据成功: {period}")
                return True
                
        except Exception as e:
            logger.error(f"保存快乐8数据失败: {e}")
            return False
    
    def get_latest_ssq(self) -> Optional[Dict[str, Any]]:
        """获取最新双色球开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT period, draw_date, red_balls, blue_ball, prize_pool, sales_amount
                    FROM ssq_results 
                    ORDER BY period DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'period': result[0],
                        'draw_date': result[1],
                        'red_balls': json.loads(result[2]),
                        'blue_ball': result[3],
                        'prize_pool': result[4],
                        'sales_amount': result[5]
                    }
                return None
                
        except Exception as e:
            logger.error(f"获取最新双色球数据失败: {e}")
            return None
    
    def get_latest_3d(self) -> Optional[Dict[str, Any]]:
        """获取最新福彩3D开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT period, draw_date, numbers, sales_amount
                    FROM fucai3d_results 
                    ORDER BY period DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'period': result[0],
                        'draw_date': result[1],
                        'numbers': json.loads(result[2]),
                        'sales_amount': result[3]
                    }
                return None
                
        except Exception as e:
            logger.error(f"获取最新福彩3D数据失败: {e}")
            return None
    
    def get_latest_qlc(self) -> Optional[Dict[str, Any]]:
        """获取最新七乐彩开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT period, draw_date, basic_numbers, special_number, prize_pool, sales_amount
                    FROM qilecai_results 
                    ORDER BY period DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'period': result[0],
                        'draw_date': result[1],
                        'basic_numbers': json.loads(result[2]),
                        'special_number': result[3],
                        'prize_pool': result[4],
                        'sales_amount': result[5]
                    }
                return None
                
        except Exception as e:
            logger.error(f"获取最新七乐彩数据失败: {e}")
            return None
    
    def get_latest_kl8(self) -> Optional[Dict[str, Any]]:
        """获取最新快乐8开奖结果"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT period, draw_date, numbers, prize_pool, sales_amount
                    FROM kuaile8_results 
                    ORDER BY period DESC 
                    LIMIT 1
                """)
                
                result = cursor.fetchone()
                if result:
                    return {
                        'period': result[0],
                        'draw_date': result[1],
                        'numbers': json.loads(result[2]),
                        'prize_pool': result[3],
                        'sales_amount': result[4]
                    }
                return None
                
        except Exception as e:
            logger.error(f"获取最新快乐8数据失败: {e}")
            return None
    
    def get_historical_data(self, lottery_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """获取历史开奖数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if lottery_type == "双色球":
                    cursor.execute("""
                        SELECT period, draw_date, red_balls, blue_ball, prize_pool, sales_amount
                        FROM ssq_results 
                        ORDER BY period DESC 
                        LIMIT ?
                    """, (limit,))
                    
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            'period': row[0],
                            'draw_date': row[1],
                            'red_balls': json.loads(row[2]),
                            'blue_ball': row[3],
                            'prize_pool': row[4],
                            'sales_amount': row[5]
                        })
                    return results
                    
                elif lottery_type == "福彩3D":
                    cursor.execute("""
                        SELECT period, draw_date, numbers, sales_amount
                        FROM fucai3d_results 
                        ORDER BY period DESC 
                        LIMIT ?
                    """, (limit,))
                    
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            'period': row[0],
                            'draw_date': row[1],
                            'numbers': json.loads(row[2]),
                            'sales_amount': row[3]
                        })
                    return results
                    
                elif lottery_type == "七乐彩":
                    cursor.execute("""
                        SELECT period, draw_date, basic_numbers, special_number, prize_pool, sales_amount
                        FROM qilecai_results 
                        ORDER BY period DESC 
                        LIMIT ?
                    """, (limit,))
                    
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            'period': row[0],
                            'draw_date': row[1],
                            'basic_numbers': json.loads(row[2]),
                            'special_number': row[3],
                            'prize_pool': row[4],
                            'sales_amount': row[5]
                        })
                    return results
                    
                elif lottery_type == "快乐8":
                    cursor.execute("""
                        SELECT period, draw_date, numbers, prize_pool, sales_amount
                        FROM kuaile8_results 
                        ORDER BY period DESC 
                        LIMIT ?
                    """, (limit,))
                    
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            'period': row[0],
                            'draw_date': row[1],
                            'numbers': json.loads(row[2]),
                            'prize_pool': row[3],
                            'sales_amount': row[4]
                        })
                    return results
                    
                return []
                
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return []
    
    def update_number_statistics(self, lottery_type: str, numbers: List[str]):
        """更新号码统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                current_date = datetime.now().isoformat()
                
                for number in numbers:
                    cursor.execute("""
                        INSERT OR REPLACE INTO number_statistics 
                        (lottery_type, number, frequency, last_appearance, updated_at)
                        VALUES (
                            ?, ?, 
                            COALESCE((SELECT frequency + 1 FROM number_statistics 
                                     WHERE lottery_type = ? AND number = ?), 1),
                            ?, ?
                        )
                    """, (lottery_type, number, lottery_type, number, current_date, current_date))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"更新号码统计失败: {e}")
    
    def get_number_statistics(self, lottery_type: str) -> Dict[str, int]:
        """获取号码统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT number, frequency 
                    FROM number_statistics 
                    WHERE lottery_type = ?
                    ORDER BY frequency DESC
                """, (lottery_type,))
                
                return {row[0]: row[1] for row in cursor.fetchall()}
                
        except Exception as e:
            logger.error(f"获取号码统计失败: {e}")
            return {}
    
    def log_sync(self, lottery_type: str, records_count: int, status: str = 'success', 
                error_message: Optional[str] = None):
        """记录数据同步日志"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO sync_logs 
                    (lottery_type, sync_date, records_count, status, error_message)
                    VALUES (?, ?, ?, ?, ?)
                """, (lottery_type, datetime.now().isoformat(), records_count, status, error_message))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"记录同步日志失败: {e}")
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                info = {}
                
                # 统计各表记录数
                tables = ['ssq_results', 'fucai3d_results', 'qilecai_results', 'kuaile8_results']
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    info[table] = count
                
                # 获取最新同步时间
                cursor.execute("""
                    SELECT lottery_type, MAX(sync_date) 
                    FROM sync_logs 
                    GROUP BY lottery_type
                """)
                sync_info = {row[0]: row[1] for row in cursor.fetchall()}
                info['last_sync'] = sync_info
                
                return info
                
        except Exception as e:
            logger.error(f"获取数据库信息失败: {e}")
            return {}
