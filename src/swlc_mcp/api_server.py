"""
SWLC MCP Server HTTP API
为MCP服务器提供HTTP接口，支持其他应用通过HTTP请求访问彩票数据
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .server import SWLCService, LotteryResult

# 导入新模块
from .predictor import PredictionManager
from .backtest import BacktestEngine

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="SWLC MCP API",
    description="提供彩票开奖数据查询和分析的HTTP API接口",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化彩票服务
lottery_service = SWLCService()

# 初始化预测和回测引擎
prediction_manager = PredictionManager()
backtest_engine = BacktestEngine()

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "SWLC MCP API服务",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "latest": "/api/latest/{lottery_type}",
            "historical": "/api/historical/{lottery_type}",
            "analysis": "/api/analysis/{lottery_type}",
            "random": "/api/random/{lottery_type}",
            "sync": "/api/sync/{lottery_type}",
            "force_sync": "/api/force-sync/{lottery_type}",
            "database": "/api/database/info",
            "predict": "/api/predict/{lottery_type}",
            "backtest": "/api/backtest/{lottery_type}",
            "settings": "/api/settings"
        },
        "description": {
            "sync": "智能同步数据（根据数据新鲜度自动决定是否需要更新）",
            "force_sync": "强制同步数据（忽略数据新鲜度检查，直接从网络获取最新数据）"
        }
    }

@app.get("/api/latest/{lottery_type}")
async def get_latest_result(lottery_type: str):
    """获取最新开奖结果"""
    try:
        if lottery_type == "ssq":
            result = await lottery_service.get_ssq_latest()
        elif lottery_type == "3d":
            result = await lottery_service.get_3d_latest()
        elif lottery_type == "qlc":
            result = await lottery_service.get_qlc_latest()
        elif lottery_type == "kl8":
            result = await lottery_service.get_kl8_latest()
        else:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        if result:
            return {
                "success": True,
                "data": {
                    "lottery_type": result.lottery_type,
                    "period": result.period,
                    "draw_date": result.draw_date,
                    "numbers": result.numbers,
                    "special_numbers": result.special_numbers,
                    "prize_pool": result.prize_pool,
                    "sales_amount": result.sales_amount
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="未找到开奖数据")
            
    except Exception as e:
        logger.error(f"获取最新开奖结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historical/{lottery_type}")
async def get_historical_data(
    lottery_type: str, 
    periods: int = Query(10, ge=1, le=1000, description="获取期数")
):
    """获取历史开奖数据"""
    try:
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        results = await lottery_service.get_historical_data(chinese_type, periods)
        
        if results:
            data = []
            for result in results:
                data.append({
                    "lottery_type": result.lottery_type,
                    "period": result.period,
                    "draw_date": result.draw_date,
                    "numbers": result.numbers,
                    "special_numbers": result.special_numbers,
                    "prize_pool": result.prize_pool,
                    "sales_amount": result.sales_amount
                })
            
            return {
                "success": True,
                "data": data,
                "count": len(data),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="未找到历史数据")
            
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analysis/{lottery_type}")
async def get_number_analysis(
    lottery_type: str,
    periods: int = Query(30, ge=5, le=1000, description="分析期数")
):
    """获取号码分析"""
    try:
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        results = await lottery_service.get_historical_data(chinese_type, periods)
        
        if not results:
            raise HTTPException(status_code=404, detail="未找到数据进行分析")
        
        # 基于本次 results 直接计算频次，严格遵循 periods
        def norm(n: str) -> str:
            try:
                return f"{int(n):02d}"
            except Exception:
                return n
        freq: Dict[str, int] = {}
        for r in results:
            for n in (r.numbers or []):
                nn = norm(n)
                freq[nn] = freq.get(nn, 0) + 1
            for n in (r.special_numbers or []):
                nn = norm(n)
                freq[nn] = freq.get(nn, 0) + 1
        
        # 若 distinct 数量过少，用候选全集补0计数，保证可选数量
        def build_universe(ltype: str) -> List[str]:
            if ltype == "双色球":
                # 红1-33 + 蓝1-16
                red = [f"{i:02d}" for i in range(1, 34)]
                blue = [f"{i:02d}" for i in range(1, 17)]
                return list(dict.fromkeys(red + blue))
            if ltype == "福彩3D":
                return [str(i) for i in range(10)]
            if ltype == "七乐彩":
                base = [f"{i:02d}" for i in range(1, 31)]
                return base
            if ltype == "快乐8":
                return [f"{i:02d}" for i in range(1, 81)]
            return []
        universe = build_universe(chinese_type)
        for u in universe:
            if u not in freq:
                freq[u] = 0
        
        # 排序与分配热门/冷门
        sorted_all = sorted(freq.items(), key=lambda x: (-x[1], int(x[0]) if x[0].isdigit() else 0))
        asc_all = list(reversed(sorted_all))
        total = len(sorted_all)
        
        # 至少5，最多10，且确保另一侧也能至少5
        k = max(5, min(10, total // 2))
        if total - k < 5:
            k = max(5, total - 5)
        k = max(5, min(k, total))
        
        hot_pairs = sorted_all[:k]
        hot_set = {k for k, _ in hot_pairs}
        cold_pairs: List[Any] = []
        for knum, v in asc_all:
            if knum in hot_set:
                continue
            cold_pairs.append((knum, v))
            if len(cold_pairs) >= k:
                break
        
        hot_obj = {k2: int(v2) for k2, v2 in hot_pairs}
        cold_obj = {k2: int(v2) for k2, v2 in cold_pairs}
        
        return {
            "success": True,
            "data": {
                "lottery_type": chinese_type,
                "analysis_periods": periods,
                "hot_numbers": hot_obj,
                "cold_numbers": cold_obj,
                # 连号分析暂保留为基于 analyze 的结果（不影响热门冷门）
                "consecutive_analysis": lottery_service.analyze_numbers(results).consecutive_analysis
            },
            "timestamp": datetime.now().isoformat()
        }
            
    except Exception as e:
        logger.error(f"获取号码分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/random/{lottery_type}")
async def get_random_numbers(
    lottery_type: str,
    count: int = Query(1, ge=1, le=10, description="生成组数")
):
    """生成随机号码"""
    try:
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        results = []
        for i in range(count):
            random_result = lottery_service.generate_random_numbers(chinese_type)
            results.append({
                "index": i + 1,
                "lottery_type": chinese_type,
                "numbers": random_result,
                "format": random_result['format']
            })
        
        return {
            "success": True,
            "data": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"生成随机号码失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/{lottery_type}")
async def sync_lottery_data(
    lottery_type: str,
    periods: int = Query(10, ge=1, le=50, description="同步期数")
):
    """同步彩票数据"""
    try:
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        # 获取历史数据（这会自动触发网络同步）
        results = await lottery_service.get_historical_data(chinese_type, periods)
        
        return {
            "success": True,
            "message": f"成功同步{chinese_type}数据",
            "data": {
                "lottery_type": chinese_type,
                "synced_periods": len(results),
                "requested_periods": periods
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"同步彩票数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/force-sync/{lottery_type}")
async def force_sync_lottery_data(
    lottery_type: str,
    periods: int = Query(20, ge=1, le=1000, description="强制同步期数")
):
    """强制同步彩票数据（忽略数据新鲜度检查）"""
    try:
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        # 强制同步数据
        sync_result = await lottery_service.force_sync_data(chinese_type, periods)
        
        if sync_result["success"]:
            return {
                "success": True,
                "message": sync_result["message"],
                "data": {
                    "lottery_type": chinese_type,
                    "synced_count": sync_result["synced_count"],
                    "total_available": sync_result["total_available"],
                    "requested_periods": periods
                },
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail=sync_result["message"])
        
    except Exception as e:
        logger.error(f"强制同步彩票数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/info")
async def get_database_info():
    """获取数据库信息"""
    try:
        info = lottery_service.db.get_database_info()
        
        return {
            "success": True,
            "data": {
                "record_counts": {
                    "双色球": info.get('ssq_results', 0),
                    "福彩3D": info.get('fucai3d_results', 0),
                    "七乐彩": info.get('qilecai_results', 0),
                    "快乐8": info.get('kuaile8_results', 0)
                },
                "last_sync": info.get('last_sync', {}),
                "database_path": lottery_service.db.db_path
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取数据库信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/predict/{lottery_type}")
async def get_prediction(
    lottery_type: str,
    method: str = Query("rule", description="预测方法: rule"),
    count: int = Query(5, ge=1, le=20, description="预测组数"),
    strategy: str = Query("all", description="策略: all|balanced|cold_recovery|hot_focus|interval_balance|contrarian")
):
    """获取预测结果（支持策略）"""
    try:
        # 统一类型映射
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D",
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        chinese_type = lottery_type_map.get(lottery_type, lottery_type)
        
        # 历史数据用于预测
        hist = await lottery_service.get_historical_data(chinese_type, 120)
        if not hist:
            raise HTTPException(status_code=404, detail="历史数据不足")
        history_dict = [{
            'period': r.period,
            'numbers': r.numbers,
            'special_numbers': r.special_numbers,
            'draw_date': r.draw_date
        } for r in hist]
        
        preds = await prediction_manager.predict(chinese_type, history_dict, method=method, count=count, strategy=strategy)
        
        out = []
        for p in preds:
            out.append({
                'numbers': p.numbers,
                'special_numbers': p.special_numbers,
                'confidence': p.confidence,
                'method': p.method,
                'timestamp': p.timestamp,
                'metadata': p.metadata
            })
        return {
            "success": True,
            "data": out,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"预测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/backtest/{lottery_type}")
async def run_backtest(
    lottery_type: str,
    window_size: int = Query(100, ge=50, le=500, description="窗口大小"),
    step: int = Query(50, ge=10, le=100, description="步长")
):
    """运行回测分析"""
    try:
        # 类型映射
        lottery_type_map = {
            "ssq": "双色球",
            "3d": "福彩3D", 
            "qlc": "七乐彩",
            "kl8": "快乐8"
        }
        
        chinese_type = lottery_type_map.get(lottery_type)
        if not chinese_type:
            raise HTTPException(status_code=400, detail="不支持的彩票类型")
        
        # 获取历史数据
        historical_data = await lottery_service.get_historical_data(chinese_type, window_size * 2)
        
        if len(historical_data) < window_size:
            raise HTTPException(status_code=400, detail=f"历史数据不足，需要至少{window_size}期数据")
        
        # 转换为字典格式
        history_dict = []
        for result in historical_data:
            history_dict.append({
                'period': result.period,
                'numbers': result.numbers,
                'special_numbers': result.special_numbers,
                'draw_date': result.draw_date
            })
        
        # 执行回测
        backtest_result = await backtest_engine.run_backtest(
            lottery_type, history_dict, window_size=window_size, step=step
        )
        
        return {
            "success": True,
            "data": {
                "total_periods": backtest_result.total_periods,
                "average_accuracy": backtest_result.average_accuracy,
                "best_strategy": backtest_result.best_strategy,
                "strategy_performance": backtest_result.strategy_performance,
                "chart_data": backtest_result.chart_data,
                "timestamp": backtest_result.timestamp
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"回测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """获取系统设置"""
    try:
        # 这里将来会从配置文件或数据库读取设置
        settings = {
            "deepseek_key": "",
            "openai_key": "",
            "prediction_methods": ["rule", "ai", "hybrid"],
            "default_lottery_type": "ssq"
        }
        
        return {
            "success": True,
            "data": settings,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"获取设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings")
async def save_settings(settings: Dict[str, Any]):
    """保存系统设置"""
    try:
        # 这里将来会保存到配置文件或数据库
        logger.info(f"保存设置: {settings}")
        
        return {
            "success": True,
            "message": "设置保存成功",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"保存设置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "SWLC MCP API",
        "timestamp": datetime.now().isoformat(),
        "database": "connected" if lottery_service.db else "disconnected"
    }

def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """启动API服务器"""
    logger.info(f"启动HTTP API服务器: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_api_server()
