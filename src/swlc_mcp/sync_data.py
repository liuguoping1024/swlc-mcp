#!/usr/bin/env python3
"""
彩票数据同步脚本
用于手动同步彩票开奖数据到本地SQLite数据库
"""

import asyncio
import logging
from datetime import datetime
from .server import SWLCService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def sync_all_lottery_data():
    """同步所有彩票类型的数据"""
    service = SWLCService()
    
    lottery_types = ["双色球", "福彩3D", "七乐彩", "快乐8"]
    
    for lottery_type in lottery_types:
        logger.info(f"开始同步{lottery_type}数据...")
        try:
            # 同步最近30期数据
            results = await service.get_historical_data(lottery_type, 30)
            if results:
                logger.info(f"成功同步{lottery_type}数据{len(results)}期")
                # 记录同步日志
                service.db.log_sync(lottery_type, len(results))
            else:
                logger.warning(f"同步{lottery_type}数据失败")
                service.db.log_sync(lottery_type, 0, 'failed', '获取数据失败')
        except Exception as e:
            logger.error(f"同步{lottery_type}数据出错: {e}")
            service.db.log_sync(lottery_type, 0, 'failed', str(e))

async def sync_specific_lottery(lottery_type: str, periods: int = 30):
    """同步指定彩票类型的数据"""
    service = SWLCService()
    
    logger.info(f"开始同步{lottery_type}数据...")
    try:
        results = await service.get_historical_data(lottery_type, periods)
        if results:
            logger.info(f"成功同步{lottery_type}数据{len(results)}期")
            service.db.log_sync(lottery_type, len(results))
        else:
            logger.warning(f"同步{lottery_type}数据失败")
            service.db.log_sync(lottery_type, 0, 'failed', '获取数据失败')
    except Exception as e:
        logger.error(f"同步{lottery_type}数据出错: {e}")
        service.db.log_sync(lottery_type, 0, 'failed', str(e))

def show_database_info():
    """显示数据库信息"""
    service = SWLCService()
    info = service.db.get_database_info()
    
    print("\n=== 本地数据库统计信息 ===")
    print("各彩票类型记录数：")
    for table, count in info.items():
        if table != 'last_sync':
            lottery_name = {
                'ssq_results': '双色球',
                'fucai3d_results': '福彩3D', 
                'qilecai_results': '七乐彩',
                'kuaile8_results': '快乐8'
            }.get(table, table)
            print(f"- {lottery_name}: {count}期")
    
    if 'last_sync' in info and info['last_sync']:
        print("\n最新同步时间：")
        for lottery_type, sync_time in info['last_sync'].items():
            print(f"- {lottery_type}: {sync_time}")

async def main():
    """主函数"""
    print("彩票数据同步工具")
    print("=" * 50)
    
    while True:
        print("\n请选择操作：")
        print("1. 同步所有彩票类型数据")
        print("2. 同步双色球数据")
        print("3. 同步福彩3D数据")
        print("4. 同步七乐彩数据")
        print("5. 同步快乐8数据")
        print("6. 查看数据库信息")
        print("0. 退出")
        
        choice = input("\n请输入选择 (0-6): ").strip()
        
        if choice == "0":
            print("退出程序")
            break
        elif choice == "1":
            await sync_all_lottery_data()
        elif choice == "2":
            periods = int(input("请输入同步期数 (默认30): ") or "30")
            await sync_specific_lottery("双色球", periods)
        elif choice == "3":
            periods = int(input("请输入同步期数 (默认30): ") or "30")
            await sync_specific_lottery("福彩3D", periods)
        elif choice == "4":
            periods = int(input("请输入同步期数 (默认30): ") or "30")
            await sync_specific_lottery("七乐彩", periods)
        elif choice == "5":
            periods = int(input("请输入同步期数 (默认30): ") or "30")
            await sync_specific_lottery("快乐8", periods)
        elif choice == "6":
            show_database_info()
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    asyncio.run(main())
