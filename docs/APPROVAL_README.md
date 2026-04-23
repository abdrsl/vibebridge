# 审批系统使用说明

## 功能概述

审批系统允许管理员对高风险命令进行审批。当用户执行被标记为高风险（high/critical）的命令时，系统会自动创建审批请求并发送到指定的飞书群聊。管理员可以在飞书中通过点击卡片按钮或发送命令进行审批。

## 配置方法

### 1. 设置审批群聊ID

在环境变量中设置审批群聊ID：

```bash
export FEISHU_APPROVAL_CHAT_ID="oc_xxxxxxxxxxxxxxxxxxxxxxxx"
```

或者在配置文件中设置：

```yaml
feishu:
  # ... 其他配置
  approval_chat_id: "oc_xxxxxxxxxxxxxxxxxxxxxxxx"
```

### 2. 配置审批规则

在 `~/.config/vibebridge/config.yaml` 中配置审批规则：

```yaml
approval:
  enabled: true
  default_level: "low"  # 默认风险等级
  rules:
    # 规则1：所有提供者的危险操作
    - provider: "*"
      pattern: "rm -rf|delete.*all|drop.*table|format.*disk"
      level: "critical"
    
    # 规则2：OpenCode的敏感操作
    - provider: "opencode"
      pattern: "git push.*--force|git reset.*--hard|npm run.*build.*--production"
      level: "high"
    
    # 规则3：文件系统操作
    - provider: "*"
      pattern: "chmod.*777|chown.*root|sudo.*"
      level: "high"
```

## 使用方法

### 用户端

1. 用户发送高风险命令，例如：`rm -rf /tmp/important`
2. 系统检测到高风险，返回：
   ```
   ⏸️ 该命令被标记为 critical 风险，已提交审批。
   请求ID: 73d95f6a
   请等待管理员在飞书中批准。
   
   命令: `rm -rf /tmp/important`
   ```

### 管理员端

#### 方法1：通过飞书卡片审批

1. 审批请求会自动发送到配置的审批群聊
2. 管理员点击卡片上的按钮：
   - ✅ 允许一次：仅批准本次执行
   - ✅ 永久允许：永久批准此类命令
   - ❌ 拒绝：拒绝执行

#### 方法2：通过命令审批

在飞书中发送命令：
```
/approve 73d95f6a allow-once
/approve 73d95f6a allow-always
/approve 73d95f6a deny
```

### 审批结果通知

审批通过后：
- 用户会收到通知：`✅ 审批通过，任务已开始执行。`
- 任务会继续执行

审批拒绝后：
- 用户会收到通知：`❌ 命令被拒绝执行。`

## 技术实现

### 文件结构

```
src/vibebridge/
├── approval.py          # 审批管理器
├── tasks.py            # 集成审批逻辑
└── server.py           # 处理卡片交互
```

### 核心类

1. **ApprovalManager**: 管理审批请求的生命周期
2. **ApprovalRequest**: 审批请求数据模型
3. **TaskOrchestrator**: 集成审批检查和处理

### 数据存储

审批请求保存在：
```
~/.local/share/vibebridge/approvals.json
```

## 测试方法

### 1. 启动服务

```bash
cd /home/user/workspace/vibebridge
vibebridge start
```

### 2. 测试高风险命令

在飞书中发送：
```
rm -rf /tmp/test
```

### 3. 查看审批请求

检查日志：
```bash
vibebridge logs
```

### 4. 进行审批

在审批群聊中点击卡片按钮或发送命令。

## 注意事项

1. **审批群聊配置**：必须正确配置 `FEISHU_APPROVAL_CHAT_ID`
2. **权限控制**：只有审批群聊中的管理员可以进行审批
3. **请求过期**：审批请求24小时后自动过期
4. **数据持久化**：审批记录会保存到本地文件
5. **兼容性**：支持飞书卡片交互和文本命令两种方式

## 故障排除

### 问题1：审批请求未发送

检查：
1. 审批群聊ID是否正确配置
2. 飞书API权限是否足够
3. 网络连接是否正常

### 问题2：卡片按钮无效

检查：
1. 飞书事件订阅是否正确配置
2. Webhook URL是否正确
3. 卡片格式是否符合飞书要求

### 问题3：审批后任务未执行

检查：
1. 审批状态是否正确更新
2. 任务信息是否保存
3. 后台任务是否正常启动