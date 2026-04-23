#!/usr/bin/env python3
"""
小水自动演示脚本

按顺序自动向小水发送所有演示 prompt，每条等上一条跑完再发下一条。
你只需要打开浏览器看着就行。

Usage:
    1. 先启动小水（双击桌面图标或 python3 server.py）
    2. 确认浏览器打开了 http://localhost:8002
    3. 在浏览器里点「+ 新对话」
    4. 另开一个终端，cd 到小水目录，运行:
       python3 auto_demo.py

    默认每条 prompt 之间间隔 3 秒，可以改 PAUSE_BETWEEN_PROMPTS
"""

import json
import time
import urllib.request
import urllib.error

# ── 配置 ──────────────────────────────────────────────────────
API_URL = "http://localhost:8002"
PAUSE_BETWEEN_PROMPTS = 3   # 每条 prompt 之间的停顿（秒）
PAUSE_AFTER_NEW_CHAT = 1    # 创建新对话后的停顿（秒）

# ── 演示脚本 ──────────────────────────────────────────────────
# 每个场景是一个独立对话
DEMO_SCRIPTS = [
    {
        "title": "场景 1：编码能力",
        "prompt": """用 HTML + JavaScript 帮我做一个像素风跑酷小游戏，要求：
1. 角色是一个方块，按空格键跳跃
2. 地面有随机出现的障碍物，角色碰到就游戏结束
3. 有计分系统，存活时间越长分数越高
4. 像素风配色，背景深色
保存到 runner.html""",
    },
    {
        "title": "场景 2：计划管理 (TodoWrite)",
        "prompt": "我想做一个命令行番茄钟 Python 脚本。先用 TodoWrite 列出完整的实现计划，然后一步步完成，每完成一步就更新状态",
    },
    {
        "title": "场景 3：子 agent 派遣 (Task)",
        "prompt": "派一个子 agent 去调研 agent.py 这个文件，告诉我里面定义了哪些类和函数，每个是做什么的。要求只返回简明总结",
    },
    {
        "title": "场景 4：持久化任务 (TaskManager)",
        "prompt": """帮我创建三个任务：
1. 写 README 文档
2. 添加单元测试
3. 部署到服务器

让任务 2 依赖任务 1（task 2 blockedBy task 1），任务 3 依赖任务 2。创建完列出所有任务""",
    },
    {
        "title": "场景 5：技能加载 (Skills)",
        "prompt": "先告诉我你现在有哪些可用的 skills，然后加载 code-review 这个 skill，按照里面的方法审查 agent.py 前 100 行代码",
    },
    {
        "title": "场景 6：团队协作 (TeammateManager)",
        "prompt": "创建一个叫 alice 的队友，角色是 coder，让她在后台统计当前目录所有 .py 文件的总行数，并把结果保存到 line_count.txt",
    },
    {
        "title": "场景 7：后台任务 (Background)",
        "prompt": '在后台运行一个 5 秒的长任务：sleep 5 && echo "任务完成"。不要等它，立刻帮我列出当前目录所有文件。之后再检查后台任务的状态',
    },
    {
        "title": "场景 8：工具清单 (Tools / MCP)",
        "prompt": "你有哪些可用的工具？请列出所有工具名称并按类型分组",
    },
    {
        "title": "场景 9：上下文压缩 (Compact)",
        "prompt": "手动触发一次对话压缩，解释一下压缩做了什么",
    },
]


# ── API 调用 ──────────────────────────────────────────────────
def api_post(path: str, data: dict) -> dict:
    req = urllib.request.Request(
        API_URL + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def new_chat() -> str:
    """创建新对话，返回 sid"""
    resp = api_post("/api/new", {})
    return resp["sid"]


def send_message(sid: str, msg: str) -> dict:
    """发送消息给小水，等待完整响应"""
    return api_post("/api/chat", {"sid": sid, "msg": msg})


# ── 主流程 ──────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("💧 小水自动演示开始")
    print("=" * 60 + "\n")

    # 先测试 API 是否可达
    try:
        urllib.request.urlopen(API_URL + "/api/chats", timeout=5)
    except (urllib.error.URLError, TimeoutError):
        print("❌ 无法连接到小水 (http://localhost:8002)")
        print("   请先启动小水服务：python3 server.py")
        return
    print("✅ 已连接到小水\n")

    total = len(DEMO_SCRIPTS)
    for i, scene in enumerate(DEMO_SCRIPTS, 1):
        print(f"\n{'─' * 60}")
        print(f"[{i}/{total}] {scene['title']}")
        print(f"{'─' * 60}")
        print(f"📝 Prompt:\n{scene['prompt'][:200]}{'...' if len(scene['prompt']) > 200 else ''}\n")

        # 每个场景开一个新对话
        sid = new_chat()
        print(f"🆕 新对话创建: {sid}")
        time.sleep(PAUSE_AFTER_NEW_CHAT)

        # 发送 prompt
        print(f"📤 发送 prompt，等待小水响应...")
        start = time.time()
        try:
            result = send_message(sid, scene["prompt"])
            elapsed = time.time() - start
            tool_count = len(result.get("tool_calls", []))
            text_len = len(result.get("text", ""))
            print(f"✅ 完成 (耗时 {elapsed:.1f}s, {tool_count} 次工具调用, 返回 {text_len} 字)")
        except Exception as e:
            print(f"❌ 出错: {e}")

        # 等待一下再进入下一个场景，方便观众看清楚
        if i < total:
            print(f"⏸  等待 {PAUSE_BETWEEN_PROMPTS} 秒后进入下一场景...")
            time.sleep(PAUSE_BETWEEN_PROMPTS)

    print("\n" + "=" * 60)
    print("🎉 所有场景演示完成！")
    print("=" * 60)
    print("\n💡 提示：刷新浏览器 http://localhost:8002 可以看到左侧所有对话\n")


if __name__ == "__main__":
    main()
