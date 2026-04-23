# 💧 小水对话版

一个基于 Claude 的 AI 编程助手，带 Web 聊天界面。

## 功能特性

- **AI 编程助手**: 基于 Claude API 的智能编程辅助
- **Web 聊天界面**: 美观的深色主题 UI，支持对话历史
- **完整工具集**: 
  - 文件操作 (read/write/edit)
  - Todo 管理
  - 子 Agent 派遣
  - 持久化任务系统
  - 技能加载
  - 团队协作
  - 后台任务
  - 上下文压缩
- **番茄钟**: 内置命令行番茄钟工具
- **自动演示**: 可运行演示脚本展示各种功能
- **代码统计**: 2617 行 Python 代码

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：

```bash
pip install anthropic python-dotenv fastapi uvicorn
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env` 并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 Anthropic API Key：

```
ANTHROPIC_API_KEY=your-api-key-here
MODEL_ID=claude-sonnet-4-20250514
```

### 3. 启动服务

方式一：直接运行 Python

```bash
python server.py
```

方式二：使用启动脚本（macOS）

```bash
open 启动小水对话版.command
```

然后打开浏览器访问 http://localhost:8002

### 4. 开始对话

点击「+ 新对话」开始与小水聊天。

## 项目结构

```
小水对话版/
├── agent.py              # 核心 Agent 实现
├── server.py            # Web 服务器 (FastAPI)
├── pomodoro.py         # 番茄钟工具
├── auto_demo.py        # 自动演示脚本
├── requirements.txt    # Python 依赖
├── .env                # 环境变量 (本地)
├── .env.example        # 环境变量示例
├── .gitignore          # Git 忽略配置
├── runner.html         # Web UI
├── pixel-runner.html   # 像素风格 Web UI
├── 启动小水对话版.command  # macOS 启动脚本
├── skills/             # 技能插件目录
│   ├── agent-builder/ # Agent 构建器
│   ├── code-review/   # 代码审查
│   ├── mcp-builder/  # MCP 工具构建
│   └── pdf/          # PDF 处理
├── .chats/            # 对话历史存储
├── .tasks/            # 任务系统存储
├── .team/             # 团队成员存储
├── .transcripts/      # 记录存储
└── README.md          # 本文档
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | (必填) |
| `MODEL_ID` | 使用的模型 ID | `claude-sonnet-4-20250514` |
| `SERVER_PORT` | 服务器端口 | `8002` |
| `MAX_TOKENS` | 最大 token 数 | `4096` |

## REPL 命令

在终端直接运行 `python agent.py` 可以进入交互模式：

| 命令 | 说明 |
|------|------|
| `/compact` | 手动压缩对话上下文 |
| `/tasks` | 查看所有任务 |
| `/team` | 查看团队成员 |
| `/inbox` | 查看收件箱 |
| `/help` | 显示帮助信息 |
| `exit` 或 `quit` | 退出程序 |

## Skills

可用的技能加载：

### agent-builder
构建自定义 Agent
```bash
# 在对话中使用
load skill agent-builder
```

### code-review
代码审查
```bash
# 在对话中使用
load skill code-review
```

### mcp-builder
MCP 工具构建
```bash
# 在对话中使用
load skill mcp-builder
```

### pdf
PDF 处理
```bash
# 在对话中使用
load skill pdf
```

## 番茄钟

```bash
python pomodoro.py
```

支持命令: `start`, `pause`, `resume`, `reset`, `skip`, `stats`

### 使用示例

```bash
python pomodoro.py start   # 开始番茄钟
python pomodoro.py pause  # 暂停
python pomodoro.py resume # 继续
python pomodoro.py reset # 重置
python pomodoro.py stats # 查看统计
```

## 自动演示

```bash
python auto_demo.py
```

演示各种功能的用法（需先启动 server.py）

## 技术栈

- **AI**: Anthropic Claude API
- **Web 框架**: FastAPI + Uvicorn
- **前端**: 原生 HTML/CSS/JS (无框架依赖)
- **存储**: JSON 文件

## 常见问题

### Q: API Key 怎么获取？
A: 访问 [Anthropic Console](https://console.anthropic.com/) 注册账号并创建 API Key。

### Q: 服务器无法启动？
A: 请检查：
1. 端口 8002 是否被占用
2. `.env` 文件是否正确配置
3. 依赖是否正确安装

### Q: 对话历史在哪里？
A: 对话历史保存在 `.chats/` 目录下的 JSON 文件中。

### Q: 如何查看代码行数？
A: 项目目前共有 2617 行 Python 代码。

### Q: 如何在 macOS 上快速启动？
A: 双击 `启动小水对话版.command` 文件即可启动服务。

## 贡献指南

欢迎提交 Pull Request！请确保：

1. 代码符合项目风格
2. 添加必要的文档
3. 测试新功能

## License

MIT