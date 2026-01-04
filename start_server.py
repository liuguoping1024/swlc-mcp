#!/usr/bin/env python3
"""
SWLC MCP服务器启动脚本
支持启动MCP服务器或HTTP API服务器
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.swlc_mcp.server import create_swlc_server, async_main

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SWLC MCP服务器启动脚本")
    parser.add_argument(
        "--mode", 
        choices=["mcp", "api", "web"], 
        default="mcp",
        help="启动模式: mcp (MCP服务器), api (HTTP API服务器), web (Web服务，包含API和前端)"
    )
    parser.add_argument(
        "--host", 
        default="0.0.0.0",
        help="HTTP服务器主机地址 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="HTTP服务器端口 (默认: 8000)"
    )
    
    args = parser.parse_args()
    
    if args.mode == "mcp":
        logger.info("启动MCP服务器...")
        try:
            asyncio.run(async_main())
        except KeyboardInterrupt:
            logger.info("MCP服务器已停止")
        except Exception as e:
            logger.error(f"MCP服务器启动失败: {e}")
            sys.exit(1)
    
    elif args.mode == "api":
        from src.swlc_mcp.api_server import start_api_server
        logger.info(f"启动HTTP API服务器: http://{args.host}:{args.port}")
        try:
            start_api_server(host=args.host, port=args.port)
        except KeyboardInterrupt:
            logger.info("HTTP API服务器已停止")
        except Exception as e:
            logger.error(f"HTTP API服务器启动失败: {e}")
            sys.exit(1)
    
    elif args.mode == "web":
        from src.swlc_mcp.api_server import start_api_server
        logger.info(f"启动Web服务（API + 前端）: http://{args.host}:{args.port}")
        try:
            start_api_server(host=args.host, port=args.port)
        except KeyboardInterrupt:
            logger.info("Web服务已停止")
        except Exception as e:
            logger.error(f"Web服务启动失败: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
