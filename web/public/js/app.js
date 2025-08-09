// 全局变量
let currentLotteryType = 'ssq';
let chartInstance = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// 初始化应用
function initializeApp() {
    // 绑定导航事件
    bindNavigationEvents();
    
    // 绑定彩票类型选择事件
    bindLotteryTypeEvents();
    
    // 加载初始数据
    loadDashboardData();
    
    // 启动健康检查
    startHealthCheck();
    
    // 初始化图表
    initializeCharts();
}

// 绑定导航事件
function bindNavigationEvents() {
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // 更新导航按钮状态
            navButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // 更新标签页内容
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(targetTab).classList.add('active');
            
            // 加载对应标签页的数据
            loadTabData(targetTab);
        });
    });
}

// 绑定彩票类型选择事件
function bindLotteryTypeEvents() {
    const lotterySelect = document.getElementById('lotteryType');
    lotterySelect.addEventListener('change', function() {
        currentLotteryType = this.value;
        loadDashboardData();
    });
}

// 加载仪表板数据
async function loadDashboardData() {
    await Promise.all([
        loadLatestResult(),
        loadHistoricalData(),
        loadNumberStats()
    ]);
}

// 加载标签页数据
function loadTabData(tabName) {
    switch(tabName) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'prediction':
            // 预测页面不需要预加载数据
            break;
        case 'backtest':
            // 回测页面不需要预加载数据
            break;
        case 'settings':
            loadSettings();
            break;
    }
}

// 加载最新开奖结果
async function loadLatestResult() {
    const resultDiv = document.getElementById('latestResult');
    resultDiv.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
        const response = await fetch(`/api/latest/${currentLotteryType}`);
        const data = await response.json();
        
        if (data.success) {
            const result = data.data;
            resultDiv.innerHTML = `
                <div class="lottery-info">
                    <div class="period">第${result.period}期</div>
                    <div class="date">${result.draw_date}</div>
                </div>
                <div class="lottery-numbers">
                    ${result.numbers.map(num => 
                        `<div class="number-ball red-ball">${num}</div>`
                    ).join('')}
                    ${result.special_numbers ? result.special_numbers.map(num => 
                        `<div class="number-ball blue-ball">${num}</div>`
                    ).join('') : ''}
                </div>
                <div class="lottery-details">
                    <div>奖池: ${formatMoney(result.prize_pool)}</div>
                    <div>销售额: ${formatMoney(result.sales_amount)}</div>
                </div>
            `;
        } else {
            resultDiv.innerHTML = '<div class="error">获取数据失败</div>';
        }
    } catch (error) {
        console.error('加载最新开奖失败:', error);
        resultDiv.innerHTML = '<div class="error">网络错误</div>';
    }
}

// 加载历史数据
async function loadHistoricalData() {
    const dataDiv = document.getElementById('historicalData');
    const periods = document.getElementById('periods').value;
    
    dataDiv.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
        const response = await fetch(`/api/draws?lottery_type=${currentLotteryType}&periods=${periods}`);
        const data = await response.json();
        
        if (data.success && data.data) {
            const historyData = data.data;
            let html = '<table class="history-table">';
            html += '<thead><tr><th>期号</th><th>开奖日期</th><th>开奖号码</th></tr></thead><tbody>';
            
            historyData.forEach(item => {
                html += `
                    <tr>
                        <td>${item.period}</td>
                        <td>${item.draw_date}</td>
                        <td>
                            <div class="lottery-numbers">
                                ${item.numbers.map(num => 
                                    `<div class="number-ball red-ball">${num}</div>`
                                ).join('')}
                                ${item.special_numbers ? item.special_numbers.map(num => 
                                    `<div class="number-ball blue-ball">${num}</div>`
                                ).join('') : ''}
                            </div>
                        </td>
                    </tr>
                `;
            });
            
            html += '</tbody></table>';
            dataDiv.innerHTML = html;
        } else {
            dataDiv.innerHTML = '<div class="error">获取历史数据失败</div>';
        }
    } catch (error) {
        console.error('加载历史数据失败:', error);
        dataDiv.innerHTML = '<div class="error">网络错误</div>';
    }
}

// 加载号码统计
async function loadNumberStats() {
    const statsDiv = document.getElementById('numberStats');
    statsDiv.innerHTML = '<div class="loading">加载中...</div>';
    
    try {
        const response = await fetch(`/api/analysis/${currentLotteryType}?periods=30`);
        const data = await response.json();
        
        if (data.success && data.data) {
            const stats = data.data;
            let html = '<div class="stats-grid">';
            
            // 热门号码
            if (stats.hot_numbers) {
                html += '<div class="stat-section">';
                html += '<h4>热门号码</h4>';
                html += '<div class="number-list">';
                stats.hot_numbers.forEach(num => {
                    html += `<span class="stat-number hot">${num}</span>`;
                });
                html += '</div></div>';
            }
            
            // 冷门号码
            if (stats.cold_numbers) {
                html += '<div class="stat-section">';
                html += '<h4>冷门号码</h4>';
                html += '<div class="number-list">';
                stats.cold_numbers.forEach(num => {
                    html += `<span class="stat-number cold">${num}</span>`;
                });
                html += '</div></div>';
            }
            
            html += '</div>';
            statsDiv.innerHTML = html;
        } else {
            statsDiv.innerHTML = '<div class="error">获取统计数据失败</div>';
        }
    } catch (error) {
        console.error('加载号码统计失败:', error);
        statsDiv.innerHTML = '<div class="error">网络错误</div>';
    }
}

// 生成预测
async function generatePrediction() {
    const resultsDiv = document.getElementById('predictionResults');
    const method = document.getElementById('predictionMethod').value;
    const count = document.getElementById('predictionCount').value;
    
    resultsDiv.innerHTML = '<div class="loading">生成预测中...</div>';
    
    try {
        const response = await fetch(`/api/predict/${currentLotteryType}?method=${method}&count=${count}`);
        const data = await response.json();
        
        if (data.success && data.data) {
            const predictions = data.data;
            let html = '';
            
            predictions.forEach((prediction, index) => {
                html += `
                    <div class="prediction-item">
                        <h4>预测组合 ${index + 1}</h4>
                        <div class="lottery-numbers">
                            ${prediction.numbers.map(num => 
                                `<div class="number-ball red-ball">${num}</div>`
                            ).join('')}
                            ${prediction.special_numbers ? prediction.special_numbers.map(num => 
                                `<div class="number-ball blue-ball">${num}</div>`
                            ).join('') : ''}
                        </div>
                        <div class="prediction-meta">
                            <span>置信度: ${prediction.confidence}%</span>
                            <span>方法: ${prediction.method}</span>
                        </div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        } else {
            resultsDiv.innerHTML = '<div class="error">生成预测失败</div>';
        }
    } catch (error) {
        console.error('生成预测失败:', error);
        resultsDiv.innerHTML = '<div class="error">网络错误</div>';
    }
}

// 运行回测
async function runBacktest() {
    const resultsDiv = document.getElementById('backtestResults');
    const windowSize = document.getElementById('windowSize').value;
    const stepSize = document.getElementById('stepSize').value;
    
    resultsDiv.innerHTML = '<div class="loading">运行回测中...</div>';
    
    try {
        const response = await fetch(`/api/backtest/${currentLotteryType}?window_size=${windowSize}&step=${stepSize}`);
        const data = await response.json();
        
        if (data.success && data.data) {
            const backtestResults = data.data;
            let html = `
                <div class="backtest-summary">
                    <h3>回测结果摘要</h3>
                    <div class="summary-stats">
                        <div class="stat-item">
                            <span class="stat-label">总测试期数:</span>
                            <span class="stat-value">${backtestResults.total_periods}</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">平均命中率:</span>
                            <span class="stat-value">${backtestResults.average_accuracy}%</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-label">最佳策略:</span>
                            <span class="stat-value">${backtestResults.best_strategy}</span>
                        </div>
                    </div>
                </div>
            `;
            
            resultsDiv.innerHTML = html;
            
            // 如果有图表数据，绘制图表
            if (backtestResults.chart_data) {
                drawBacktestChart(backtestResults.chart_data);
            }
        } else {
            resultsDiv.innerHTML = '<div class="error">回测失败</div>';
        }
    } catch (error) {
        console.error('运行回测失败:', error);
        resultsDiv.innerHTML = '<div class="error">网络错误</div>';
    }
}

// 保存设置
async function saveSettings() {
    const deepseekKey = document.getElementById('deepseekKey').value;
    const openaiKey = document.getElementById('openaiKey').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                deepseek_key: deepseekKey,
                openai_key: openaiKey
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showMessage('设置保存成功', 'success');
        } else {
            showMessage('设置保存失败', 'error');
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        showMessage('网络错误', 'error');
    }
}

// 加载设置
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('deepseekKey').value = data.data.deepseek_key || '';
            document.getElementById('openaiKey').value = data.data.openai_key || '';
        }
    } catch (error) {
        console.error('加载设置失败:', error);
    }
}

// 初始化图表
function initializeCharts() {
    const chartContainer = document.getElementById('chartContainer');
    if (chartContainer) {
        chartInstance = echarts.init(chartContainer);
    }
}

// 绘制回测图表
function drawBacktestChart(chartData) {
    if (!chartInstance) return;
    
    const option = {
        title: {
            text: '回测结果趋势',
            left: 'center'
        },
        tooltip: {
            trigger: 'axis'
        },
        legend: {
            data: ['命中率', '预测准确度'],
            top: 30
        },
        xAxis: {
            type: 'category',
            data: chartData.periods
        },
        yAxis: {
            type: 'value',
            min: 0,
            max: 100
        },
        series: [
            {
                name: '命中率',
                type: 'line',
                data: chartData.accuracy,
                smooth: true
            },
            {
                name: '预测准确度',
                type: 'line',
                data: chartData.precision,
                smooth: true
            }
        ]
    };
    
    chartInstance.setOption(option);
}

// 启动健康检查
function startHealthCheck() {
    checkHealth();
    setInterval(checkHealth, 30000); // 每30秒检查一次
}

// 检查健康状态
async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const statusElement = document.getElementById('serverStatus');
        const serverOk = (typeof data.mcp_server === 'string' && data.mcp_server === 'healthy')
            || (data.mcp_server && data.mcp_server.status === 'healthy');
        
        if (serverOk) {
            statusElement.innerHTML = '🟢 服务器正常';
            statusElement.className = 'status-item';
        } else {
            statusElement.innerHTML = '🔴 服务器异常';
            statusElement.className = 'status-item error';
        }
        
        document.getElementById('lastUpdate').textContent = `最后更新: ${data.timestamp || ''}`;
    } catch (error) {
        const statusElement = document.getElementById('serverStatus');
        statusElement.innerHTML = '🔴 连接失败';
        statusElement.className = 'status-item error';
    }
}

// 显示消息
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    document.body.appendChild(messageDiv);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}

// 格式化金额
function formatMoney(amount) {
    if (!amount) return '0';
    return new Intl.NumberFormat('zh-CN', {
        style: 'currency',
        currency: 'CNY'
    }).format(amount);
}

// 全局函数，供HTML调用
window.loadHistoricalData = loadHistoricalData;
window.generatePrediction = generatePrediction;
window.runBacktest = runBacktest;
window.saveSettings = saveSettings;
