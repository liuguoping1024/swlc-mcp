const express = require('express');
const axios = require('axios');
const cors = require('cors');
const path = require('path');
const moment = require('moment');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Python MCP Server API 配置
const MCP_API_BASE = process.env.MCP_API_BASE || 'http://127.0.0.1:8001';

// 代理 MCP 服务器的数据
app.get('/api/draws', async (req, res) => {
  try {
    const { lottery_type = 'ssq', periods = 50 } = req.query;
    const response = await axios.get(`${MCP_API_BASE}/api/historical/${lottery_type}`, {
      params: { periods: parseInt(periods) }
    });
    res.json(response.data);
  } catch (error) {
    console.error('获取开奖数据失败:', error.message);
    res.status(500).json({ 
      error: '获取开奖数据失败', 
      details: error.message 
    });
  }
});

app.get('/api/latest/:lottery_type', async (req, res) => {
  try {
    const { lottery_type } = req.params;
    const response = await axios.get(`${MCP_API_BASE}/api/latest/${lottery_type}`);
    res.json(response.data);
  } catch (error) {
    console.error('获取最新开奖失败:', error.message);
    res.status(500).json({ 
      error: '获取最新开奖失败', 
      details: error.message 
    });
  }
});

app.get('/api/analysis/:lottery_type', async (req, res) => {
  try {
    const { lottery_type } = req.params;
    const { periods = 30 } = req.query;
    const response = await axios.get(`${MCP_API_BASE}/api/analysis/${lottery_type}`, {
      params: { periods: parseInt(periods) }
    });
    res.json(response.data);
  } catch (error) {
    console.error('获取分析数据失败:', error.message);
    res.status(500).json({ 
      error: '获取分析数据失败', 
      details: error.message 
    });
  }
});

app.get('/api/predict/:lottery_type', async (req, res) => {
  try {
    const { lottery_type } = req.params;
    const { method = 'rule', count = 5 } = req.query;
    
    const response = await axios.get(`${MCP_API_BASE}/api/predict/${lottery_type}`, {
      params: { method, count: parseInt(count) }
    });
    res.json(response.data);
  } catch (error) {
    console.error('获取预测数据失败:', error.message);
    res.status(500).json({ 
      error: '获取预测数据失败', 
      details: error.message 
    });
  }
});

app.get('/api/backtest/:lottery_type', async (req, res) => {
  try {
    const { lottery_type } = req.params;
    const { window_size = 100, step = 50 } = req.query;
    
    const response = await axios.get(`${MCP_API_BASE}/api/backtest/${lottery_type}`, {
      params: { window_size: parseInt(window_size), step: parseInt(step) }
    });
    res.json(response.data);
  } catch (error) {
    console.error('获取回测数据失败:', error.message);
    res.status(500).json({ 
      error: '获取回测数据失败', 
      details: error.message 
    });
  }
});

// 健康检查
app.get('/api/health', async (req, res) => {
  try {
    const response = await axios.get(`${MCP_API_BASE}/api/health`);
    res.json({
      frontend: 'healthy',
      mcp_server: response.data,
      timestamp: moment().format('YYYY-MM-DD HH:mm:ss')
    });
  } catch (error) {
    res.status(503).json({
      frontend: 'healthy',
      mcp_server: 'unhealthy',
      error: error.message,
      timestamp: moment().format('YYYY-MM-DD HH:mm:ss')
    });
  }
});

// 前端路由
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// 错误处理中间件
app.use((err, req, res, next) => {
  console.error('服务器错误:', err);
  res.status(500).json({ 
    error: '服务器内部错误',
    message: err.message 
  });
});

app.listen(PORT, () => {
  console.log(`🚀 前端服务器运行在 http://localhost:${PORT}`);
  console.log(`📡 连接到MCP服务器: ${MCP_API_BASE}`);
  console.log(`⏰ 启动时间: ${moment().format('YYYY-MM-DD HH:mm:ss')}`);
});
