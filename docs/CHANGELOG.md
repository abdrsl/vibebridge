# 更新日志

所有OpenCode-Feishu Bridge项目的显著更改都将记录在此文件中。

格式基于[Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
并且本项目遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.1] - 2026-04-01

### 新增
- WebSocket长连接支持，提供更稳定的飞书通信
- 增强的加密功能，支持完整的Feishu事件订阅加密/解密流程
- 新增TEST_WEBSOCKET_GUIDE.md文档，提供WebSocket测试指南
- 新增requirements-dev.txt，分离开发和生产依赖

### 变更
- 优化多智能体系统启动和停止流程
- 改进会话管理，修复内存泄漏问题
- 更新README.md，提供更完整的项目文档
- 重构.gitignore，更好地管理临时文件

### 修复
- 修复飞书Webhook处理中的并发问题
- 修复OpenCode任务流中的进度更新延迟
- 修复环境变量加载顺序问题
- 修复测试中的期望值不匹配问题

## [1.0.0] - 2026-03-30

### 新增
- 初始发布：基于FastAPI的多智能体系统
- 6个专门智能体：协调器、OpenCode代理、飞书代理、LLM代理、内存代理、技能代理
- 完整的Feishu Webhook集成，支持v1/v2格式
- OpenCode CLI完整集成，支持任务创建、跟踪和监控
- 环境变量加密系统，支持敏感配置安全存储
- Docker和Docker Compose部署支持
- 完整的文档系统（14个文档文件）

### 核心功能
- 多智能体协调系统，基于消息总线通信
- 飞书交互式卡片系统（开始、进度、结果、错误、帮助卡片）
- Server-Sent Events (SSE)实时进度流
- 自定义命令系统，支持6个内置命令
- 会话管理系统，基于Redis存储
- 速率限制和API保护
- 隧道自动管理（ngrok/localtunnel）

### 技术栈
- **后端**: FastAPI, Uvicorn, Pydantic
- **AI集成**: LiteLLM, LangGraph, OpenAI, Anthropic, Google Generative AI
- **数据库**: Redis, Qdrant (向量数据库)
- **安全**: Cryptography, PyCryptodome, SlowAPI
- **测试**: Pytest, Pytest-asyncio
- **部署**: Docker, Docker Compose

## 版本说明

### 版本号规则
- **主版本号**: 不兼容的API修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 发布周期
- **主要版本**: 每3-6个月，包含重大功能更新
- **次要版本**: 每1-2个月，包含新功能和改进
- **修订版本**: 根据需要，包含错误修复和安全更新

### 支持策略
- **当前版本**: 完全支持，接收所有更新
- **上一个主要版本**: 安全更新和关键错误修复
- **更早版本**: 社区支持，不保证官方更新

## 迁移指南

### 从v1.0.0升级到v1.0.1
1. 更新依赖：`pip install -r requirements.txt`
2. 检查环境变量，确保加密配置正确
3. 重启服务：`./manage.sh restart`
4. 验证WebSocket连接（可选）

### 向后兼容性
- v1.0.1完全向后兼容v1.0.0的API
- 所有环境变量配置保持相同
- 现有会话和数据自动迁移

## 贡献者

感谢所有为OpenCode-Feishu Bridge项目做出贡献的人！

### 核心贡献者
- 项目创始团队
- 文档编写团队
- 测试和QA团队

### 特别感谢
- Feishu开放平台团队
- OpenCode CLI开发团队
- 开源社区贡献者

---

*此更新日志从v1.0.0版本开始记录。*