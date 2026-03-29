# 自定义指令系统

## 🎯 功能概述

自定义指令系统允许你通过Feishu发送特定文字来触发预设操作，包括：

- **清空session** - 清空当前会话
- **kimi** - 切换到Kimi K2.5模型  
- **deepseek** - 切换到Deepseek Reasoner模型
- **git 提交** - 执行Git提交操作
- **启动服务器** - 启动服务器

## 📁 文件说明

```
/home/user/workspace/ai-project/
├── config/
│   └── commands.json           # 指令配置文件（永久有效）
├── app/
│   ├── command_processor.py    # 指令处理器
│   └── feishu_webhook_handler.py  # 已集成指令处理
└── manage_commands.py          # 指令管理工具
```

## 🚀 使用方法

### 方式1: 通过Feishu发送指令

在Feishu中直接发送以下文字：

| 指令 | 说明 | 需要确认 |
|------|------|----------|
| `清空session` | 清空当前所有活跃会话 | ❌ 否 |
| `kimi` | 切换到Kimi K2.5模型 | ❌ 否 |
| `deepseek` | 切换到Deepseek Reasoner模型 | ❌ 否 |
| `git 提交` | 执行git add/commit/push | ✅ 是 |
| `启动服务器` | 启动本地服务器 | ❌ 否 |

### 方式2: 管理指令（添加/删除/修改）

```bash
cd /home/user/workspace/ai-project

# 查看所有指令
python manage_commands.py list

# 添加新指令
python manage_commands.py add

# 删除指令
python manage_commands.py remove

# 编辑指令
python manage_commands.py edit

# 显示帮助
python manage_commands.py help
```

## 🔧 配置文件详解

配置文件位置：`config/commands.json`

```json
{
  "version": "1.0",
  "commands": {
    "指令名称": {
      "action": "动作类型",
      "description": "描述",
      "confirm": false,
      "response": "响应消息"
    }
  },
  "models": {
    "模型ID": {
      "name": "显示名称",
      "provider": "提供商",
      "model_id": "API模型ID",
      "api_key_env": "API密钥环境变量名"
    }
  }
}
```

### 内置动作类型

1. **clear_session** - 清空会话
   - 关闭用户的所有活跃会话
   - 无需参数

2. **switch_model** - 切换模型
   - 需要指定 `model` 参数
   - 可选值：`kimi-k2.5`, `deepseek-reasoner`, `default`

3. **git_commit** - Git提交
   - 自动执行 git add .
   - 自动执行 git status
   - 自动执行 git commit -m "Update from Feishu bot"
   - 自动执行 git push
   - 需要确认

4. **start_server** - 启动服务器
   - 检查服务器是否已在运行
   - 如未运行则启动
   - 等待启动完成并返回状态

5. **custom** - 自定义（预留）
   - 可以添加自定义逻辑

## 📝 添加自定义指令示例

### 示例1: 添加"查看状态"指令

```bash
python manage_commands.py add
```

输入：
```
指令名称: 查看状态
选择动作类型 (1-5): 1  # clear_session
描述: 查看系统当前状态
需要确认? (y/n): n
响应消息: 📊 当前系统运行正常
```

### 示例2: 直接编辑配置文件

```bash
# 编辑配置文件
nano /home/user/workspace/ai-project/config/commands.json
```

添加：
```json
{
  "commands": {
    "查看状态": {
      "action": "custom",
      "description": "查看系统状态",
      "confirm": false,
      "response": "✅ 系统运行正常"
    }
  }
}
```

## 🎨 自定义响应消息

可以修改指令的响应消息使其更友好：

```json
{
  "清空session": {
    "action": "clear_session",
    "description": "清空当前会话",
    "confirm": false,
    "response": "🗑️ 已清空所有会话，让我们重新开始吧！"
  }
}
```

## ⚙️ 模型配置

在 `config/commands.json` 的 `models` 部分配置模型：

```json
{
  "models": {
    "kimi-k2.5": {
      "name": "Kimi K2.5",
      "provider": "moonshot",
      "model_id": "moonshot-v1-128k",
      "api_key_env": "MOONSHOT_API_KEY"
    },
    "deepseek-reasoner": {
      "name": "Deepseek Reasoner",
      "provider": "deepseek",
      "model_id": "deepseek-reasoner",
      "api_key_env": "DEEPSEEK_API_KEY"
    }
  }
}
```

## 🔄 持久化说明

**所有配置永久保存在**：
- `config/commands.json` - 指令配置
- 配置文件随代码一起保存
- 服务器重启后依然有效

## 🔍 故障排除

### 指令不生效

1. 检查配置文件是否存在：
   ```bash
   cat /home/user/workspace/ai-project/config/commands.json
   ```

2. 检查服务器是否重启（加载新配置）：
   ```bash
   ./manage.sh restart
   ```

3. 查看日志：
   ```bash
   tail -f /home/user/workspace/ai-project/logs/server.log | grep -E "(Command|指令)"
   ```

### 修改后不生效

修改配置文件后需要重启服务器：
```bash
./manage.sh restart
```

或者等待自动重启（如果配置了自动启动）

## 🎉 现在可以使用了！

在Feishu中发送：
- `清空session` - 清空会话
- `kimi` - 切换模型
- `git 提交` - Git操作

所有指令都已集成到系统中，永久有效！