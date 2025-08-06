# SWLC MCP Server

这是一个专为上海地区设计的彩票信息查询MCP（Model Context Protocol）服务器，提供双色球、福彩3D、七乐彩等彩票的开奖查询和分析功能。

## 功能特性

- 🎯 **最新开奖查询**：获取双色球、福彩3D、七乐彩的最新开奖结果
- 📊 **历史数据查询**：获取指定期数的历史开奖数据
- 📈 **号码分析**：提供热号、冷号统计和频率分析
- 🎲 **随机推荐**：生成随机彩票号码推荐
- 🔍 **智能统计**：提供详细的开奖统计信息

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
```bash
swlc-mcp
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
- `periods`: 获取期数（1-100，默认10）

### `analyze_numbers`
分析号码统计信息
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `periods`: 分析期数（5-100，默认30）

### `generate_random_numbers`
生成随机号码推荐
- `lottery_type`: 彩票类型（双色球/福彩3D/七乐彩/快乐8）
- `count`: 生成组数（1-10，默认1）

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

## 技术栈

- **Python 3.10+**
- **MCP Python SDK**：用于构建MCP服务器
- **httpx**：异步HTTP客户端
- **Pydantic**：数据验证和序列化
- **python-dateutil**：日期处理

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