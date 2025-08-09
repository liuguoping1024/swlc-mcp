#!/usr/bin/env python3
"""
HTTP API测试脚本
用于测试SWLC MCP服务器的HTTP API接口
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any

# API基础URL
BASE_URL = "http://localhost:8000"

async def test_api_endpoint(session: aiohttp.ClientSession, endpoint: str, method: str = "GET", params: Dict = None) -> Dict[str, Any]:
    """测试API端点"""
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            async with session.get(url, params=params) as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else await response.text()
                }
        elif method == "POST":
            async with session.post(url, params=params) as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.status == 200 else await response.text()
                }
    except Exception as e:
        return {
            "status": "error",
            "data": str(e)
        }

async def run_api_tests():
    """运行API测试"""
    print("🚀 开始测试SWLC MCP HTTP API")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        
        # 1. 测试根路径
        print("\n1. 测试API根路径")
        result = await test_api_endpoint(session, "/")
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ API根路径测试通过")
        else:
            print(f"❌ API根路径测试失败: {result['data']}")
        
        # 2. 测试健康检查
        print("\n2. 测试健康检查")
        result = await test_api_endpoint(session, "/api/health")
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 健康检查测试通过")
        else:
            print(f"❌ 健康检查测试失败: {result['data']}")
        
        # 3. 测试获取最新开奖结果
        print("\n3. 测试获取最新开奖结果")
        lottery_types = ["ssq", "3d", "qlc", "kl8"]
        for lottery_type in lottery_types:
            result = await test_api_endpoint(session, f"/api/latest/{lottery_type}")
            print(f"{lottery_type.upper()}: 状态码 {result['status']}")
            if result['status'] == 200:
                print(f"✅ {lottery_type} 最新开奖结果获取成功")
            else:
                print(f"❌ {lottery_type} 最新开奖结果获取失败: {result['data']}")
        
        # 4. 测试获取历史数据
        print("\n4. 测试获取历史数据")
        result = await test_api_endpoint(session, "/api/historical/ssq", params={"periods": 5})
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 历史数据获取成功")
        else:
            print(f"❌ 历史数据获取失败: {result['data']}")
        
        # 5. 测试号码分析
        print("\n5. 测试号码分析")
        result = await test_api_endpoint(session, "/api/analysis/ssq", params={"periods": 10})
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 号码分析成功")
        else:
            print(f"❌ 号码分析失败: {result['data']}")
        
        # 6. 测试生成随机号码
        print("\n6. 测试生成随机号码")
        result = await test_api_endpoint(session, "/api/random/ssq", params={"count": 3})
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 随机号码生成成功")
        else:
            print(f"❌ 随机号码生成失败: {result['data']}")
        
        # 7. 测试数据库信息
        print("\n7. 测试数据库信息")
        result = await test_api_endpoint(session, "/api/database/info")
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 数据库信息获取成功")
        else:
            print(f"❌ 数据库信息获取失败: {result['data']}")
        
        # 8. 测试数据同步
        print("\n8. 测试数据同步")
        result = await test_api_endpoint(session, "/api/sync/ssq", method="POST", params={"periods": 5})
        print(f"状态码: {result['status']}")
        if result['status'] == 200:
            print("✅ 数据同步成功")
        else:
            print(f"❌ 数据同步失败: {result['data']}")
    
    print("\n" + "=" * 50)
    print("🎉 API测试完成")

def main():
    """主函数"""
    print("请确保HTTP API服务器已启动: python start_server.py --mode api")
    print("服务器地址: http://localhost:8000")
    
    try:
        asyncio.run(run_api_tests())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")

if __name__ == "__main__":
    main()
