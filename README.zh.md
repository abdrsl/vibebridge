     1|# VibeBridge
     2|
     3|[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
     4|[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
     5|
     6|> **本地 AI 编程代理缺失的 IM 网关。**
     7|
     8|在 60 秒内将 AI 编程代理部署到团队聊天中。VibeBridge 将**飞书**与本地 vibe-coding 工具（OpenCode、Kimi Code CLI、Claude Code）连接起来，让你可以直接从聊天消息中编写、审查和部署代码。
     9|
    10|---
    11|
    12|## ✨ 核心特性
    13|
    14|- **手机远程写代码**：在地铁上@机器人让它帮你写脚本。
    15|- **团队协作**：产品经理、设计师直接在飞书群里提需求，AI 自动执行并回传结果截图。
    16|- **多工具自由切换**：用 `/kimi`、`/claude`、`/openc` 前缀随时切换底层 Agent。
    17|- **权限口令控制**：在消息中包含秘密口令可授予敏感操作的最高权限。
    18|- **一键部署**：支持 systemd 自启动、Docker、一键安装脚本。
    19|
    20|---
    21|
    22|## 🚀 快速开始
    23|
    24|### 一键安装
    25|
    26|```bash
    27|curl -fsSL https://raw.githubusercontent.com/akliedrak/vibebridge/main/install.sh | bash
    28|```
    29|
    30|### 配置
    31|
    32|交互式配置：
    33|
    34|```bash
    35|vibebridge init
    36|```
    37|
    38|自动化配置（适合 CI/脚本）：
    39|
    40|```bash
    41|export FEISHU_APP_ID=cli_xxx
    42|export FEISHU_APP_SECRET=xxx
    43|export FEISHU_ENCRYPT_KEY=xxx
    44|export FEISHU_VERIFICATION_TOKEN=xxx
    45|vibebridge init --non-interactive
    46|```
    47|
    48|### 启动服务
    49|
    50|```bash
    51|# 前台调试模式
    52|vibebridge start
    53|
    54|# 注册为 systemd 用户服务，开机自启
    55|vibebridge start --install
    56|```
    57|
    58|### 在飞书中使用
    59|
    60|```
    61|@VibeBridge 写一个 FastAPI Hello World 并运行它
    62|```
    63|
    64|切换 Provider：
    65|
    66|```
    67|@VibeBridge /kimi 把这段代码改成异步的
    68|@VibeBridge /claude 设计一个电商网站的 Postgres 表结构
    69|    70|```
    71|
    72|---
    73|
    74|## 🏗️ 架构
    75|
    76|```
    77|飞书消息
    78|      ↓
    79|FeishuAdapter (Webhook / WebSocket)
    80|      ↓
    81|会话管理
    82|      ↓
    83|Provider Router
    84|      ↓
    85|┌─────────┬─────────┬─────────┬─────────┐
    86|│OpenCode │  Kimi   │ Claude  │
    87|│Provider │Provider │Provider │Provider │
    88|└─────────┴─────────┴─────────┴─────────┘
    89|      ↓
    90|流式结果卡片回传到飞书
    91|```
    92|
    93|---
    94|
    95|## 📋 Provider 支持状态
    96|
    97|| Provider | 状态 | 说明 |
    98||----------|------|------|
    99|| **OpenCode** | ✅ 完整支持 | 调用 `opencode run --format json`，流式解析输出 |
   100|   101|| **Kimi Code CLI** | 🚧 部分支持 | 需先启动 `kimi acp`，通过 ACP/MCP 协议通信 |
   102|| **Claude Code** | 🚧 部分支持 | 目前仅健康检查，执行层待实现 |
   103|
   104|---
   105|
   106|## ⚙️ 飞书开发者后台配置
   107|
   108|1. 登录 [飞书开发者后台](https://open.feishu.cn/app)
   109|2. 创建企业自建应用
   110|3. **事件订阅**：
   111|   - 请求 URL: `http://你的服务器IP:8000/im/feishu/webhook`
   112|   - Verification Token: 填入 `.env` 中的 `FEISHU_VERIFICATION_TOKEN`
   113|   - Encrypt Key: 填入 `.env` 中的 `FEISHU_ENCRYPT_KEY`
   114|   - 开启加密
   115|4. **订阅事件**：添加 `im.message.receive_v1`
   116|5. **权限管理**：开启 `im:message`、`im:message:send_as_bot`
   117|6. 发布应用，添加到目标群组
   118|
   119|---
   120|
   121|## 🛡️ 权限与安全
   122|
   123|VibeBridge 提供多层安全机制防止误操作：
   124|
   125|### 权限口令系统
   126|- **默认模式**：所有命令经过宪法检查，防止破坏性操作。
   127|- **提升权限**：在消息中包含秘密口令可跳过安全检查，获得最高权限。
   128|- **环境变量**：设置 `FEISHU_PERMIT_PASSWORD` 定义您的授权口令。
   129|
   130|### 安全特性
   131|- **宪法检查**：默认启用 OpenCode 内置安全规则。
   132|- **WebSocket 模式优化**：实时进度卡片显示最多400行输出。
   133|- **输出过滤**：工具调用行和中间步骤从最终结果中过滤。
   134|- **表格渲染**：输出中的 Markdown 表格自动在飞书卡片中渲染。
   135|- **实时进度**：WebSocket 模式下显示详细执行过程，关闭确认卡片。
   136|
   137|---
   138|
   139|## 📄 许可证
   140|
   141|MIT License — 详见 [LICENSE](LICENSE)。
   142|
   143|欢迎提交 Issue 和 PR！
   144|