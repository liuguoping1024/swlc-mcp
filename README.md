# SWLC MCP Server

这是一个专为上海地区设计的彩票信息查询MCP（Model Context Protocol）服务器，提供双色球、福彩3D、七乐彩等彩票的开奖查询和分析功能。

```
⚠️作为技术人员，我必须强调：

1、彩票本质是概率游戏，任何算法都无法保证中奖
2、历史数据只能提供参考，不能预测未来
3、建议理性购彩，将其视为娱乐而非投资
4、以上推荐纯属技术分析，请根据个人情况谨慎选择

祝您好运！
```

## 功能特性

- 🎯 **最新开奖查询**：获取双色球、福彩3D、七乐彩的最新开奖结果
- 📊 **历史数据查询**：获取指定期数的历史开奖数据
- 📈 **号码分析**：提供热号、冷号统计和频率分析
- 🎲 **随机推荐**：生成随机彩票号码推荐
- 🔍 **智能统计**：提供详细的开奖统计信息
- 💾 **本地数据存储**：使用SQLite数据库本地存储彩票数据，减少网络查询
- ⚡ **快速响应**：优先从本地数据库查询，提高查询速度
- 🔄 **数据同步**：支持手动同步最新数据到本地数据库

## 支持的彩票类型

- **双色球**：6个红球（1-33）+ 1个蓝球（1-16）
- **福彩3D**：3位数字（000-999）
- **七乐彩**：7个基本号码（1-30）+ 1个特别号码
- **快乐8**：20个号码（1-80）

## 安装方法

### 1. 克隆仓库
```bash
git clone <repository-url>
cd swlc-mcp
```

### 2. 安装依赖
```bash
pip install -e .
```

### 3. 运行服务器

#### 启动MCP服务器（用于Claude Desktop）
```bash
# 方式1: 使用启动脚本
python start_server.py --mode mcp

# 方式2: 直接运行
swlc-mcp
```

#### 启动HTTP API服务器（用于其他应用）
```bash
# 启动HTTP API服务器
python start_server.py --mode api --host 0.0.0.0 --port 8000

# 或者直接运行
python src/swlc_mcp/api_server.py
```

### 4. 数据同步（可选）
首次使用或需要更新数据时，可以运行数据同步脚本：
```bash
python src/swlc_mcp/sync_data.py
```

## MCP工具列表

### `get_latest_ssq`
获取双色球最新开奖结果

### `get_latest_3d`
获取福彩3D最新开奖结果

### `get_latest_qlc`
获取七乐彩最新开奖结果

### `get_latest_kl8`
获取快乐8最新开奖结果

### `get_historical_data`
获取历史开奖数据
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `periods`: 获取期数（1-500，默认10）
  - 如果数据库中的数据不足，会返回实际可用的数据
  - 建议首次使用先同步数据：`python src/swlc_mcp/sync_data.py`

### `analyze_numbers`
分析号码统计信息
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `periods`: 分析期数（5-500，默认30）

### `generate_random_numbers`
生成随机号码推荐
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `count`: 生成组数（1-10，默认1）

### `sync_lottery_data`
同步指定彩票类型的最新数据到本地数据库
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `periods`: 同步期数（1-50，默认10）

### `get_database_info`
获取本地数据库统计信息

## 使用示例

### 在Claude Desktop中配置

在Claude Desktop的配置文件中添加：

```json
{
  "mcpServers": {
    "swlc": {
      "command": "swlc-mcp",
      "cwd": "D:\\github\\swlc-mcp"
    }
  }
}
```

### 查询示例

- "请获取双色球最新开奖结果"
- "分析双色球最近30期的号码统计"
- "为我推荐5注七乐彩号码"
- "查看福彩3D最近10期的历史数据"
- "获取快乐8最新开奖信息"
- "同步双色球最新数据到本地数据库"
- "查看本地数据库统计信息"

<img width="400" alt="image" src="https://github.com/user-attachments/assets/cdee6ff7-4791-4fe8-9e12-e4f7261d8527" />

## 智能数据更新机制

项目实现了智能的数据更新机制，能够自动判断何时需要从网络获取最新数据：

### 数据新鲜度检查

系统会根据彩票类型的开奖频率自动检查数据的新鲜度：

- **双色球**：每周二、四、日开奖，超过3天没有新数据时自动更新
- **福彩3D**：每天开奖，超过1天没有新数据时自动更新  
- **七乐彩**：每周一、三、五开奖，超过3天没有新数据时自动更新
- **快乐8**：每天开奖，超过1天没有新数据时自动更新

### 智能更新策略

1. **自动更新**：当检测到数据过期时，系统会自动从网络获取最新数据
2. **智能回退**：如果网络获取失败，系统会返回数据库中的可用数据作为备选
3. **手动强制更新**：用户可以通过API强制同步数据，忽略数据新鲜度检查

### 更新触发时机

- 获取最新开奖结果时
- 获取历史开奖数据时  
- 获取号码分析时
- 手动调用同步API时

### 强制同步API

如果用户需要立即获取最新数据，可以使用强制同步API：

```bash
# 强制同步双色球最新20期数据
curl -X POST "http://localhost:8000/api/force-sync/ssq?periods=20"

# 强制同步福彩3D最新50期数据
curl -X POST "http://localhost:8000/api/force-sync/3d?periods=50"
```

### 数据一致性保证

- 系统会优先使用数据库中的最新数据
- 只有在数据过期或不足时才会触发网络更新
- 网络更新失败时会优雅降级到数据库数据
- 所有数据更新都会同步更新号码统计信息

## 技术栈

- **Python 3.10+**
- **MCP Python SDK**：用于构建MCP服务器
- **FastAPI**：HTTP API框架
- **Uvicorn**：ASGI服务器
- **httpx**：异步HTTP客户端
- **Pydantic**：数据验证和序列化
- **python-dateutil**：日期处理
- **SQLite**：本地数据存储

## 数据库结构

项目使用SQLite数据库存储彩票数据，包含以下表：

- `lottery_types`: 彩票类型信息
- `ssq_results`: 双色球开奖结果
- `fucai3d_results`: 福彩3D开奖结果
- `qilecai_results`: 七乐彩开奖结果
- `kuaile8_results`: 快乐8开奖结果
- `number_statistics`: 号码统计信息
- `sync_logs`: 数据同步日志

数据库文件默认保存在项目根目录的 `lottery_data.db` 文件中。

## HTTP API接口

项目提供了完整的HTTP API接口，支持其他应用通过HTTP请求访问彩票数据：

### API端点

- `GET /` - API根路径，显示所有可用端点
- `GET /api/latest/{lottery_type}` - 获取最新开奖结果
- `GET /api/historical/{lottery_type}` - 获取历史开奖数据
- `GET /api/analysis/{lottery_type}` - 获取号码分析
- `GET /api/random/{lottery_type}` - 生成随机号码
- `POST /api/sync/{lottery_type}` - 同步彩票数据
- `GET /api/database/info` - 获取数据库信息
- `GET /api/health` - 健康检查

### 支持的彩票类型

- `ssq` - 双色球
- `3d` - 福彩3D
- `qlc` - 七乐彩
- `kl8` - 快乐8

### 使用示例

```bash
# 获取双色球最新开奖结果
curl http://localhost:8000/api/latest/ssq

# 获取福彩3D最近10期历史数据
curl http://localhost:8000/api/historical/3d?periods=10

# 分析双色球最近30期号码
curl http://localhost:8000/api/analysis/ssq?periods=30

# 生成5注七乐彩随机号码
curl http://localhost:8000/api/random/qlc?count=5

# 同步双色球数据
curl -X POST http://localhost:8000/api/sync/ssq?periods=20

# 查看数据库信息
curl http://localhost:8000/api/database/info

## 测试

### API测试
```bash
# 运行API测试
python test/test_api.py
```

## 数据来源

已接入中国福利彩票官方API：
- 双色球：https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=ssq
- 福彩3D：https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=3d
- 七乐彩：https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=qlc
- 快乐8：https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice?name=kl8

所有数据均来自官方权威渠道，确保准确性和实时性。

## 注意事项

- 本工具仅供娱乐和学习用途
- 购彩需理性，请根据自身情况合理投注
- 历史数据不代表未来走势，请谨慎参考

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 致谢

本项目完全由 [Cursor](https://cursor.sh/) 完成。

## 许可证

MIT License
