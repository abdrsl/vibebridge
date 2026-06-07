# 更新日志

所有 VibeBridge 项目的显著更改都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.2.0] - 2026-06-07

### 新增
- **多 Provider 架构**：支持 OpenCode、Kimi、Claude、OpenRouter 动态切换
- **Constitutional Guard（宪法守卫）**：拦截危险命令（rm -rf、git push --force、drop database 等），需 `mysecret <命令>` 授权
- **单卡片流式更新**：任务执行过程中只更新一张卡片，避免消息刷屏
- **OpenCode Session 连续性**：首次运行自动创建 session，后续对话自动续接上下文
- **历史上下文**：自动加载最近 10 条对话历史作为上下文
- **pytest 测试框架**：新增 pytest.ini，测试覆盖率提升

### 变更
- 核心架构重构：`TaskOrchestrator` + `ProviderRouter` 替代旧版 6-agent 消息总线架构
- 飞书卡片渲染改进：移除代码块包裹，支持 Markdown 直接渲染，字符限制提升
- 进度卡片与结果卡片分离：避免 STATUS/DONE 事件重复出现在最终结果中
- 工作目录清理：删除空 agent 目录、archive、旧 venv，释放 ~427MB
- 部署方式改为 systemd user service：自动重启，端口 9000

### 修复
- 修复 OpenCode 余额不足时显示 "Unknown error" 的问题，现在显示具体 API 错误原因
- 修复错误任务仍显示 "✅ 任务完成" 的问题，改为显示 "❌ 任务失败"
- 修复 MyCompany 端口冲突：禁用 supervisord 中冲突的 vibebridge 实例
- 修复 Feishu webhook 无签名时的警告处理

## [1.0.2] - 2026-04-08

### 新增
- 模式切换功能，支持 websocket 和 webhook 模式动态切换
- 飞书交互体验优化，实时情感滚动显示
- WebSocket 自动重连机制，提升连接稳定性
- 动态进度卡片显示，增强用户反馈

### 变更
- 项目结构整理，移除根目录临时文件，规范目录结构
- 测试文件优化，合并重复测试，删除临时调试文件
- 依赖管理更新，添加 lark-oapi SDK 支持
- 配置文件保护，将 config.yaml 添加到 .gitignore

### 修复
- 修复 app_secret 截断 bug，确保飞书 API 调用正常
- 修复实时显示进度更新延迟问题
- 修复模式切换命令在 Feishu 中的实际可用性
- 修复隧道 URL 自动通知功能
- 优化隧道 URL 稳定性，添加 30 秒稳定期检查，减少频繁通知
- 增强隧道健康检查，支持 GET 和 POST 请求验证

## [1.0.1] - 2026-04-01

### 新增
- WebSocket 长连接支持，提供更稳定的飞书通信
- 增强的加密功能，支持完整的 Feishu 事件订阅加密/解密流程
- 新增 TEST_WEBSOCKET_GUIDE.md 文档，提供 WebSocket 测试指南
- 新增 requirements-dev.txt，分离开发和生产依赖

### 变更
- 优化多智能体系统启动和停止流程
- 改进会话管理，修复内存泄漏问题
- 更新 README.md，提供更完整的项目文档
- 重构 .gitignore，更好地管理临时文件

### 修复
- 修复飞书 Webhook 处理中的并发问题
- 修复 OpenCode 任务流中的进度更新延迟
- 修复环境变量加载顺序问题
- 修复测试中的期望值不匹配问题

## [1.0.0] - 2026-03-30

### 新增
- 初始发布：基于 FastAPI 的多智能体系统
- 6 个专门智能体：协调器、OpenCode 代理、飞书代理、LLM 代理、内存代理、技能代理
- 完整的 Feishu Webhook 集成，支持 v1/v2 格式
- OpenCode CLI 完整集成，支持任务创建、跟踪和监控
- 环境变量加密系统，支持敏感配置安全存储
- Docker 和 Docker Compose 部署支持
- 完整的文档系统（14 个文档文件）

### 核心功能
- 多智能体协调系统，基于消息总线通信
- 飞书交互式卡片系统（开始、进度、结果、错误、帮助卡片）
- Server-Sent Events (SSE) 实时进度流
- 自定义命令系统，支持 6 个内置命令
- 会话管理系统，基于 Redis 存储
- 速率限制和 API 保护
- 隧道自动管理（ngrok/localtunnel）

### 技术栈
- **后端**: FastAPI, Uvicorn, Pydantic
- **AI 集成**: LiteLLM, LangGraph, OpenAI, Anthropic, Google Generative AI
- **数据库**: Redis, Qdrant (向量数据库)
- **安全**: Cryptography, PyCryptodome, SlowAPI
- **测试**: Pytest, Pytest-asyncio
- **部署**: Docker, Docker Compose

## 版本说明

### 版本号规则
- **主版本号**: 不兼容的 API 修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 发布周期
- **主要版本**: 每 3-6 个月，包含重大功能更新
- **次要版本**: 每 1-2 个月，包含新功能和改进
- **修订版本**: 根据需要，包含错误修复和安全更新

### 支持策略
- **当前版本**: 完全支持，接收所有更新
- **上一个主要版本**: 安全更新和关键错误修复
- **更早版本**: 社区支持，不保证官方更新
