# AI Skills System

## Overview
This directory contains modular skills that enhance the AI assistant's capabilities with constitutional rules, session naming, and extensible skill management.

## Available Skills

### 1. Constitution (`constitution.py`)
**Purpose**: Enforces ethical and safety rules for AI interactions.

**Features**:
- Rule-based content filtering
- Priority-based enforcement (reject, warn, log)
- Default safety rules (harm prevention, privacy, compliance)

**Usage**:
```python
from skills.constitution import check_constitution

result = check_constitution(user_input)
if result["has_violations"]:
    print("Request violates constitutional rules")
```

**Default Rules**:
- Safety: Prevent harmful/dangerous content
- Helpfulness: Be honest and transparent  
- Privacy: Protect user confidentiality
- Compliance: Follow applicable laws
- Transparency: Identify as AI
- Scope: Acknowledge limitations
- Security: Promote secure practices

### 2. Session Naming (`session_naming.py`)
**Purpose**: Automatically generates descriptive session names from user input.

**Features**:
- Pattern-based extraction from user messages
- Chinese language support
- Hash-based uniqueness
- Configurable naming rules

**Usage**:
```python
from skills.session_naming import generate_session_name

session_name = generate_session_name("帮我写一个Python函数计算斐波那契数列")
# Returns: "帮我写一个Python函数计算斐波那契数列 #a1b2c3d4"
```

**Pattern Examples**:
- `写一个Python函数` → `Python函数: [名称]`
- `修复bug` → `修复: [问题]`
- `添加功能` → `功能: [名称]`
- `飞书集成` → `飞书集成`

### 3. Skill Manager (`skill_manager.py`)
**Purpose**: Central registry and management for all skills.

**Features**:
- Automatic skill loading
- Skill dependency management
- Input processing pipeline
- Skill enable/disable control

**Usage**:
```python
from skills.skill_manager import get_skill_manager

manager = get_skill_manager()
result = manager.process_input(user_message)
# Includes constitution check and session name generation
```

### 4. GitHub Skills (`github_skills.py`)
**Purpose**: Download skills from GitHub repositories.

**Features**:
- Search for skills on GitHub
- Download and install skills
- Skill repository management
- Requirements installation (optional)

**Usage**:
```python
from skills.github_skills import get_github_downloader

downloader = get_github_downloader()
skills = downloader.search_skills("opencode")
if skills:
    downloader.download_skill(skills[0].repo, skills[0].name)
```

## Integration with OpenCode

The skills system is integrated with OpenCode task creation:

```python
# In opencode_integration.py
task_id = await manager.create_task(
    user_message="用户请求",
    check_constitution=True,      # 启用宪法检查
    generate_session_name=True,   # 启用会话命名
)
```

**Automatic Features**:
1. **Constitution Check**: Logs violations (doesn't block by default)
2. **Session Naming**: Generates `session_id` from user input
3. **Skill Application**: Can be extended with additional skills

## Adding New Skills

### Option 1: Local Skill File
1. Create `your_skill.py` in the `skills/` directory
2. Implement required functions
3. Skill will be auto-loaded on next startup

### Option 2: GitHub Skill
```python
# Search and download from GitHub
downloader = get_github_downloader()
downloader.download_skill("owner/repo", "skill_name")
```

### Skill Template
```python
"""
Your Skill Description
"""

def skill_function(input_text: str, **kwargs):
    """Main skill function."""
    # Your logic here
    return result

# Optional: Export main functions
__all__ = ["skill_function"]
```

## Configuration

### Skill Manager Config
```python
from skills.skill_manager import SkillConfig, SkillManager

config = SkillConfig(
    auto_load_skills=True,
    enable_remote_skills=False,
    skills_dir=Path("/custom/skills/dir"),
)
manager = SkillManager(config)
```

### Session Naming Config
```python
from skills.session_naming import SessionNamingConfig, SessionNamer

config = SessionNamingConfig(
    default_name="默认会话",
    max_total_length=80,
    include_hash=True,
    hash_length=6,
)
namer = SessionNamer(config)
```

## Testing Skills

Run skill tests:
```bash
cd /home/user/workspace/opencode-feishu-bridge
source .venv/bin/activate

# Test constitution
python -c "from skills.constitution import check_constitution; print(check_constitution('测试输入'))"

# Test session naming  
python -c "from skills.session_naming import generate_session_name; print(generate_session_name('帮我写代码'))"

# Test skill manager
python -c "from skills.skill_manager import get_skill_manager; m=get_skill_manager(); print(m.list_skills())"
```

## Security Considerations

1. **Constitution Rules**: Modify default rules to match your requirements
2. **GitHub Downloads**: Review downloaded code before enabling
3. **Skill Permissions**: Skills run with same permissions as main application
4. **Input Validation**: All user input should pass through constitution check

## Extending the System

### Adding New Rule Types
1. Extend `ConstitutionalRule` class with custom violation detection
2. Add new patterns to `SessionNamingRule`
3. Create specialized skill base classes

### Integration Points
- **Webhook Handlers**: Add constitution check to `/feishu/webhook`
- **Task Creation**: Automatic session naming in `opencode_integration.py`
- **LLM Calls**: Pre-process prompts with skills
- **Response Filtering**: Post-process LLM output with constitution

## Troubleshooting

**Skill not loading**:
- Check file exists in `skills/` directory
- Verify Python syntax is valid
- Check for import errors in skill file

**Constitution not detecting violations**:
- Review regex patterns in `ConstitutionalRule`
- Add custom patterns for your use case
- Adjust rule priorities

**Session names too long**:
- Adjust `max_total_length` in `SessionNamingConfig`
- Modify rule extraction patterns
- Disable hash inclusion

---

## Example: Complete Integration

```python
from skills.skill_manager import get_skill_manager
from app.opencode_integration import OpenCodeManager

# Initialize
skill_manager = get_skill_manager()
opencode_manager = OpenCodeManager()

# Process user request
user_input = "用户请求内容"
skill_result = skill_manager.process_input(user_input)

if not skill_result["allowed"]:
    print(f"Request rejected: {skill_result['errors']}")
else:
    # Create OpenCode task with generated session name
    task_id = await opencode_manager.create_task(
        user_message=user_input,
        check_constitution=False,  # Already checked by skill_manager
        generate_session_name=False,  # Use skill_result session_name
    )
    
    # Set session_id from skill result
    task = await opencode_manager.get_task(task_id)
    if skill_result["session_name"]:
        task.session_id = skill_result["session_name"]
```

This provides a complete AI assistant with safety rules, automatic organization, and extensible capabilities.