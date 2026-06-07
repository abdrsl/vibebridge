# VibeBridge - 版本信息

## 当前版本: v1.2.0

**发布日期**: 2026-06-07
**状态**: 稳定发布版本
**Python 要求**: 3.10+
**许可证**: MIT License

## 版本历史

### v1.2.0 (2026-06-07)
- **多 Provider 架构**: OpenCode、Kimi、Claude、OpenRouter 动态切换
- **Constitutional Guard**: 拦截危险命令，需 `mysecret` 授权
- **单卡片流式更新**: 避免消息刷屏
- **OpenCode Session 连续性**: 自动续接对话上下文
- **历史上下文**: 自动加载最近对话历史
- **架构重构**: `TaskOrchestrator` + `ProviderRouter` 替代旧版 6-agent 架构
- **部署**: systemd user service 自动重启

### v1.0.2 (2026-04-08)
- **新增**: 模式切换功能，支持 websocket 和 webhook 动态切换
- **优化**: 飞书交互体验，实时情感滚动显示
- **增强**: WebSocket 自动重连机制
- **修复**: app_secret 截断 bug，动态进度卡片显示

### v1.0.1 (2026-04-01)
- **增强**: 加密功能增强，支持 Feishu 事件订阅加密/解密
- **新增**: WebSocket 长连接支持
- **优化**: 多智能体系统稳定性改进

### v1.0.0 (2026-03-30)
- **初始发布**: 基础稳定版本
- **核心功能**: 多智能体系统（6 个智能体）
- **集成**: Feishu Webhook 集成，OpenCode CLI 集成
- **安全**: 环境变量加密，速率限制

## 核心特性

### Provider 路由系统
- OpenCode Provider:  spawning `opencode run --format json` 流式输出
- Kimi Provider: 通过 ACP/MCP 协议集成
- Claude Provider: Claude Code CLI 集成
- OpenRouter Provider: 100+ 模型支持
- 动态切换: `/kimi`, `/claude`, `/opencode`, `/openrouter`

### 飞书集成
- WebSocket 长连接模式（推荐，无需公网 URL）
- Webhook 回调模式（备选，需要公网 URL）
- 交互式卡片系统（开始、进度、结果、错误）
- 单卡片流式更新

### Constitutional Guard
- 危险命令实时拦截（rm -rf, git push --force, drop database 等）
- 会话级授权机制: `mysecret <命令>`
- 授权状态持久化到 session

### OpenCode 集成
- 完整的 OpenCode CLI 命令支持
- Session 连续性：首次自动创建，后续自动续接
- 非 JSON 错误诊断：从 stderr 提取 API 错误原因

## 系统要求

### 软件要求
- Python 3.10+
- systemd (用于服务管理)
- opencode CLI (用于 OpenCode provider)

### 硬件要求
- 内存: 最低 2GB，推荐 4GB
- 存储: 最低 1GB 可用空间
- 网络: 稳定的互联网连接

## 部署选项

1. **systemd user service** (推荐):
   ```bash
   systemctl --user start vibebridge
   systemctl --user enable vibebridge
   ```
2. **手动运行**:
   ```bash
   python -m uvicorn vibebridge.server:app --host 0.0.0.0 --port 9000
   ```

## 配置要求

### 必需配置
- Feishu 应用 ID 和密钥
- 至少一个 AI provider 的 API 密钥（OpenCode 自带 DeepSeek）
- 加密密钥和验证令牌（飞书事件订阅）

### 可选配置
- Kimi / Claude / OpenRouter API 密钥
- Redis 连接信息（会话持久化）

## 测试状态

### 单元测试
- ✅ Provider 健康检查测试
- ✅ 飞书卡片渲染测试
- ✅ 会话管理测试
- ✅ 路由解析测试

### 集成测试
- ✅ Feishu WebSocket 连接测试
- ✅ OpenCode 任务流测试
- ✅ 多 Provider 切换测试

## 已知问题

1. **环境依赖**: 需要正确配置环境变量才能完全运行
2. **API 余额**: DeepSeek 等第三方 API 可能因余额不足而失败

## 后续计划

### 短期计划 (v1.3.0)
- 更多 Provider 支持（Gemini、Qwen 等）
- 代码质量工具集成 (ruff, black, mypy)
- 性能监控和告警

### 中期计划 (v2.0.0)
- 微服务架构重构
- 分布式智能体支持
- 多租户和权限管理

## 支持与贡献

- **问题报告**: GitHub Issues
- **文档**: 查看 `docs/` 目录
- **项目地址**: https://github.com/abdrsl/vibebridge

---

**版本维护**: 项目维护团队
**最后更新**: 2026-06-07
**项目状态**: 活跃开发中
