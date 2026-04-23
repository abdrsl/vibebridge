# OpenRouter Integration for VibeBridge

## 概述

VibeBridge 现在支持通过 OpenRouter API 访问多个 AI 模型。OpenRouter 是一个统一的 API 网关，可以访问 OpenAI、Anthropic、Google、Meta、DeepSeek 等公司的 100+ 个模型。

## 功能特性

- ✅ 支持所有 OpenRouter 上的模型
- ✅ 实时流式响应
- ✅ 模型健康检查
- ✅ 批量测试所有可用模型
- ✅ 自动配置检测
- ✅ 与现有审批系统集成

## 快速开始

### 1. 获取 OpenRouter API 密钥

1. 访问 [OpenRouter 官网](https://openrouter.ai/)
2. 注册账号并登录
3. 在 API Keys 页面创建新的 API 密钥
4. 复制你的 API 密钥

### 2. 配置环境变量

```bash
# 在 .env 文件中添加
OPENROUTER_API_KEY=your_api_key_here

# 或者直接导出
export OPENROUTER_API_KEY=your_api_key_here
```

### 3. 初始化配置

```bash
# 运行初始化命令
vibebridge init

# 或使用非交互模式
vibebridge init --non-interactive
```

初始化时会自动检测 OpenRouter API 密钥并启用该提供者。

### 4. 测试 OpenRouter 连接

```bash
# 测试基本连接
vibebridge test-openrouter

# 或使用测试脚本
python test_openrouter.py
```

### 5. 启动服务

```bash
# 启动 VibeBridge
vibebridge start
```

## 配置说明

### 配置文件示例

在 `~/.config/vibebridge/config.yaml` 中添加：

```yaml
agents:
  openrouter:
    enabled: true
    api_key: "${OPENROUTER_API_KEY}"  # 从环境变量读取
    default_model: "openai/gpt-4o"    # 默认模型
    base_url: "https://openrouter.ai/api/v1"
```

### 支持的模型示例

OpenRouter 支持 100+ 个模型，包括：

| 提供商 | 模型 | 说明 |
|--------|------|------|
| OpenAI | `openai/gpt-4o` | GPT-4 Omni |
| OpenAI | `openai/gpt-4-turbo` | GPT-4 Turbo |
| Anthropic | `anthropic/claude-3.5-sonnet` | Claude 3.5 Sonnet |
| Anthropic | `anthropic/claude-3-opus` | Claude 3 Opus |
| Google | `google/gemini-2.0-flash-exp` | Gemini 2.0 Flash |
| Meta | `meta-llama/llama-3.3-70b-instruct` | Llama 3.3 70B |
| Mistral | `mistralai/mistral-large-2411` | Mistral Large |
| DeepSeek | `deepseek/deepseek-chat` | DeepSeek Chat |
| DeepSeek | `deepseek/deepseek-reasoner` | DeepSeek Reasoner |
| Qwen | `qwen/qwen-2.5-72b-instruct` | Qwen 2.5 72B |

完整模型列表请参考 [OpenRouter 模型页面](https://openrouter.ai/models)。

## 命令行工具

### 测试所有模型

```bash
# 测试所有可用模型
vibebridge test-openrouter

# 使用测试脚本进行完整测试
python test_openrouter.py --all-models
```

### 查看服务状态

```bash
# 查看所有提供者状态
vibebridge status

# 运行诊断检查
vibebridge doctor
```

## 高级功能

### 1. 批量测试模型

```python
from vibebridge.providers.openrouter import OpenRouterProvider
import asyncio

async def test_models():
    provider = OpenRouterProvider()
    results = await provider.test_all_models()
    
    print(f"Total models: {results['total_models']}")
    for model, result in results['test_results'].items():
        if result['available']:
            print(f"✅ {model}: {result['response']}")

asyncio.run(test_models())
```

### 2. 自定义模型选择

在配置中指定不同的默认模型：

```yaml
agents:
  openrouter:
    enabled: true
    api_key: "${OPENROUTER_API_KEY}"
    default_model: "anthropic/claude-3.5-sonnet"  # 使用 Claude
    # default_model: "deepseek/deepseek-reasoner"  # 使用 DeepSeek
    # default_model: "meta-llama/llama-3.3-70b-instruct"  # 使用 Llama
```

### 3. 流式响应处理

```python
from vibebridge.providers.openrouter import OpenRouterProvider
import asyncio

async def stream_example():
    provider = OpenRouterProvider()
    
    task_id = await provider.create_task(
        prompt="写一个Python函数计算斐波那契数列",
        workdir="/tmp",
        session_id="test123"
    )
    
    async for event in provider.stream_task(task_id):
        if event.type == "text":
            print(event.content, end="", flush=True)
        elif event.type == "done":
            print("\n✅ 完成!")
            break

asyncio.run(stream_example())
```

## 故障排除

### 常见问题

1. **API 密钥无效**
   ```
   ❌ Connection failed: OpenRouter API error: 401 Unauthorized
   ```
   解决方案：检查 API 密钥是否正确，确保没有多余的空格。

2. **网络连接问题**
   ```
   ❌ Connection failed: OpenRouter API error: Connection timeout
   ```
   解决方案：检查网络连接，确保可以访问 `https://openrouter.ai`。

3. **模型不可用**
   ```
   ❌ Model not available: openai/gpt-4o
   ```
   解决方案：该模型可能暂时不可用，尝试其他模型或稍后重试。

4. **额度不足**
   ```
   ❌ API error: 402 Payment Required
   ```
   解决方案：在 OpenRouter 账户中充值或检查使用额度。

### 调试模式

```bash
# 设置调试日志级别
export LOG_LEVEL=DEBUG

# 查看详细日志
vibebridge logs -f
```

## 性能优化

### 1. 连接池配置

OpenRouter 提供者使用 HTTPX 连接池，默认配置：
- 连接超时：10秒
- 读取超时：300秒
- 连接池大小：自动管理

### 2. 模型缓存

首次获取模型列表后会缓存结果，减少 API 调用。

### 3. 错误重试

网络错误会自动重试（最多3次），提高稳定性。

## 安全注意事项

1. **API 密钥保护**
   - 不要将 API 密钥提交到版本控制系统
   - 使用环境变量或加密配置文件
   - 定期轮换 API 密钥

2. **访问控制**
   - 配置飞书群组/用户白名单
   - 启用审批系统审核敏感操作
   - 监控 API 使用情况

3. **数据隐私**
   - OpenRouter 会记录 API 调用用于计费
   - 敏感数据建议使用本地模型
   - 遵守公司数据安全政策

## 更新日志

### v1.0.0 (2024-04-19)
- ✅ 初始 OpenRouter 集成
- ✅ 支持 100+ 个模型
- ✅ 流式响应
- ✅ 批量模型测试
- ✅ 自动配置检测
- ✅ CLI 测试工具

## 相关链接

- [OpenRouter 官网](https://openrouter.ai/)
- [OpenRouter API 文档](https://openrouter.ai/docs)
- [OpenRouter 模型列表](https://openrouter.ai/models)
- [VibeBridge 主文档](../README.md)
- [审批系统文档](../APPROVAL_README.md)

## 技术支持

如有问题，请：
1. 检查本文档的故障排除部分
2. 查看服务日志：`vibebridge logs`
3. 运行诊断：`vibebridge doctor`
4. 提交 Issue 到项目仓库