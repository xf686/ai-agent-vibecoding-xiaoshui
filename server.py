#!/usr/bin/env python3
"""
小水 · Web UI with Chat History

把 agent.py (基于 s_full) 包装成 Web 聊天界面，带对话历史侧边栏。
"""

import json
import sys
import time
import uuid
from pathlib import Path

APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

import agent

from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse

# ── Chat history storage ─────────────────────────────────────────
CHATS_DIR = APP_DIR / ".chats"
CHATS_DIR.mkdir(exist_ok=True)

# ── File upload storage ─────────────────────────────────────────
UPLOADS_DIR = APP_DIR / ".uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

sessions: dict[str, list] = {}  # sid -> messages
chat_meta: dict[str, dict] = {}  # sid -> {title, created_at, updated_at}


def _chat_file(sid: str) -> Path:
    return CHATS_DIR / f"{sid}.json"


def _load_all_chats():
    """Load all chat metadata on startup."""
    for f in CHATS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            sid = f.stem
            chat_meta[sid] = {
                "title": data.get("title", "新对话"),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
            }
            sessions[sid] = data.get("messages", [])
        except Exception as e:
            print(f"[warn] failed to load chat {f}: {e}")


def _save_chat(sid: str):
    """Persist a chat to disk."""
    if sid not in sessions:
        return
    data = {
        "title": chat_meta.get(sid, {}).get("title", "新对话"),
        "created_at": chat_meta.get(sid, {}).get("created_at", time.time()),
        "updated_at": time.time(),
        "messages": _serialize_messages(sessions[sid]),
    }
    _chat_file(sid).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    chat_meta.setdefault(sid, {})["updated_at"] = data["updated_at"]


def _serialize_messages(messages: list) -> list:
    """Convert anthropic message objects to serializable dicts."""
    result = []
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            result.append({"role": msg["role"], "content": content})
        elif isinstance(content, list):
            serialized_content = []
            for block in content:
                if isinstance(block, dict):
                    serialized_content.append(block)
                elif hasattr(block, "type"):
                    d = {"type": block.type}
                    if hasattr(block, "text"):
                        d["text"] = block.text
                    if hasattr(block, "id"):
                        d["id"] = block.id
                    if hasattr(block, "name"):
                        d["name"] = block.name
                    if hasattr(block, "input"):
                        d["input"] = block.input
                    serialized_content.append(d)
                else:
                    serialized_content.append(str(block))
            result.append({"role": msg["role"], "content": serialized_content})
    return result


def _extract_display_messages(messages: list) -> list:
    """Extract user-visible messages for display (user prompts + assistant text)."""
    display = []
    for msg in messages:
        content = msg.get("content")
        if msg["role"] == "user":
            if isinstance(content, str):
                display.append({"role": "user", "text": content})
        elif msg["role"] == "assistant":
            text = ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += block.get("text", "")
                    elif hasattr(block, "text") and block.text:
                        text += block.text
            if text.strip():
                display.append({"role": "assistant", "text": text.strip()})
    return display


# ── Chat ─────────────────────────────────────────────────────────
def chat(sid: str, msg: str) -> dict:
    is_new = sid not in sessions
    if is_new:
        sessions[sid] = []
        chat_meta[sid] = {
            "title": msg[:30] + ("..." if len(msg) > 30 else ""),
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    messages = sessions[sid]
    messages.append({"role": "user", "content": msg})

    tool_log = []
    text = ""

    import builtins
    original_print = builtins.print
    tool_outputs = []

    def capture_print(*args, **kwargs):
        s = " ".join(str(a) for a in args)
        tool_outputs.append(s)
        original_print(*args, **kwargs)

    builtins.print = capture_print

    try:
        agent.agent_loop(messages)
    except Exception as e:
        text = f"错误: {e}"
    finally:
        builtins.print = original_print

    if messages:
        last = messages[-1]
        content = last.get("content", [])
        if isinstance(content, list):
            for block in content:
                if hasattr(block, "text") and block.text:
                    text += block.text
                elif isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
        elif isinstance(content, str):
            text = content

    for line in tool_outputs:
        if line.startswith("> "):
            parts = line[2:].split(": ", 1)
            tool_name = parts[0] if parts else "unknown"
            tool_output = parts[1] if len(parts) > 1 else ""
            tool_log.append({
                "tool": tool_name,
                "input": "",
                "output": tool_output[:500],
            })

    _save_chat(sid)
    return {"text": text.strip(), "tool_calls": tool_log}


# ── FastAPI ──────────────────────────────────────────────────────
app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def index():
    return PAGE


@app.get("/api/chats")
async def api_chats():
    """List all chats, sorted by updated_at desc."""
    items = []
    for sid, meta in chat_meta.items():
        items.append({
            "sid": sid,
            "title": meta.get("title", "新对话"),
            "updated_at": meta.get("updated_at", 0),
        })
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return JSONResponse(items)


@app.get("/api/chat/{sid}")
async def api_chat_get(sid: str):
    """Get messages of a specific chat for display."""
    if sid not in sessions:
        return JSONResponse({"messages": []})
    return JSONResponse({"messages": _extract_display_messages(sessions[sid])})


@app.post("/api/chat")
async def api_chat(req: Request):
    body = await req.json()
    return JSONResponse(chat(body.get("sid", "d"), body.get("msg", "")))


@app.post("/api/new")
async def api_new():
    """Create a new chat session."""
    sid = "chat_" + uuid.uuid4().hex[:8]
    return JSONResponse({"sid": sid})


@app.post("/api/delete")
async def api_delete(req: Request):
    body = await req.json()
    sid = body.get("sid")
    if sid and sid in sessions:
        sessions.pop(sid, None)
        chat_meta.pop(sid, None)
        f = _chat_file(sid)
        if f.exists():
            f.unlink()
    return JSONResponse({"ok": True})


@app.post("/api/upload")
async def api_upload(req: Request):
    """Upload a file."""
    try:
        form = await req.form()
        file = form.get("file")
        if not file:
            return JSONResponse({"error": "请选择文件"}, status_code=400)
        
        filename = file.filename
        if not filename:
            return JSONResponse({"error": "文件名不能为空"}, status_code=400)
        
        # 安全检查：防止路径穿越
        filename = Path(filename).name
        save_path = UPLOADS_DIR / filename
        
        # 如果文件已存在，加时间戳区分
        if save_path.exists():
            stem = save_path.stem
            suffix = save_path.suffix
            save_path = UPLOADS_DIR / f"{stem}_{int(time.time())}{suffix}"
        
        # 读取并保存
        content = await file.read()
        if len(content) > 100 * 1024 * 1024:  # 100MB 限制
            return JSONResponse({"error": "文件大小不能超过 100MB"}, status_code=400)
        
        save_path.write_bytes(content)
        return JSONResponse({"ok": True, "filename": save_path.name, "size": len(content)})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Load existing chats on startup
_load_all_chats()


# ── HTML ─────────────────────────────────────────────────────────
PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>小水</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@300;400;500;600&display=swap');

*{margin:0;padding:0;box-sizing:border-box}

:root{
  --bg:#0b0b10;--s1:#131319;--s2:#1b1b24;--s3:#23232f;
  --bd:#2a2a3c;--t1:#e6e6f0;--t2:#8585a0;--t3:#55556b;
  --ac:#6e8efb;--ac2:#5a7bf0;--acg:rgba(110,142,251,.12);
  --gn:#4ade80;--og:#fbbf24;--ogg:rgba(251,191,36,.08);
  --rd:#f87171;
  --r:14px;
  --mono:'JetBrains Mono',monospace;
  --sans:'Noto Sans SC',system-ui,sans-serif;
}

body{font-family:var(--sans);background:var(--bg);color:var(--t1);height:100vh;display:flex;overflow:hidden}

/* ── Sidebar ── */
.sb{width:260px;min-width:260px;background:var(--s1);border-right:1px solid var(--bd);display:flex;flex-direction:column;overflow:hidden}
.sb-h{padding:16px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:10px}
.sb-logo{width:28px;height:28px;background:linear-gradient(135deg,var(--ac),#4f6bdf);border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:600;font-size:13px;color:#fff}
.sb-title{font-size:14px;font-weight:600}
.sb-title span{color:var(--t3);font-weight:400;font-size:11px;margin-left:4px}

.new-btn{margin:12px;padding:10px 14px;background:var(--ac);border:none;border-radius:10px;color:#fff;font-size:13px;font-weight:500;cursor:pointer;transition:.15s;display:flex;align-items:center;justify-content:center;gap:6px}
.new-btn:hover{background:var(--ac2)}

.chats{flex:1;overflow-y:auto;padding:4px 8px}
.chat-item{padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:2px;transition:.12s;position:relative;display:flex;align-items:center;gap:8px}
.chat-item:hover{background:var(--s2)}
.chat-item.active{background:var(--acg);border:1px solid var(--ac)}
.chat-item-title{flex:1;font-size:13px;color:var(--t1);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.chat-item.active .chat-item-title{color:var(--ac)}
.chat-del{opacity:0;color:var(--t3);font-size:11px;padding:2px 6px;border-radius:4px;cursor:pointer;transition:.12s}
.chat-item:hover .chat-del{opacity:1}
.chat-del:hover{background:var(--rd);color:#fff}
.empty{padding:20px;text-align:center;color:var(--t3);font-size:12px}

/* ── Main ── */
.main{flex:1;display:flex;flex-direction:column;min-width:0}
header{height:52px;background:var(--s1);border-bottom:1px solid var(--bd);display:flex;align-items:center;justify-content:space-between;padding:0 20px;flex-shrink:0}
.hdr-title{font-size:14px;font-weight:500;color:var(--t2)}
.hdr-btns{display:flex;gap:6px}
.hdr-btn{background:var(--s2);border:1px solid var(--bd);color:var(--t2);height:32px;padding:0 10px;border-radius:8px;cursor:pointer;font-size:11px;display:flex;align-items:center;gap:4px;transition:.15s;font-family:var(--mono)}
.hdr-btn:hover{border-color:var(--ac);color:var(--ac)}

.wrap{flex:1;overflow:hidden;display:flex;justify-content:center}
.container{width:100%;max-width:780px;display:flex;flex-direction:column;height:100%}

#msgs{flex:1;overflow-y:auto;padding:20px 12px;display:flex;flex-direction:column;gap:16px}

.hi{flex:1;display:flex;align-items:center;justify-content:center;text-align:center;padding:32px}
.hi-icon{width:64px;height:64px;background:linear-gradient(135deg,var(--ac),#4f6bdf);border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:28px;margin:0 auto 16px;box-shadow:0 6px 24px var(--acg)}
.hi h2{font-size:20px;margin-bottom:6px}
.hi p{color:var(--t2);font-size:13px;line-height:1.7}
.hints{display:flex;flex-wrap:wrap;gap:6px;margin-top:16px;justify-content:center}
.ht{padding:7px 14px;background:var(--s2);border:1px solid var(--bd);border-radius:18px;font-size:12px;color:var(--t2);cursor:pointer;transition:.15s}
.ht:hover{border-color:var(--ac);color:var(--ac);background:var(--acg)}

.m{animation:fi .2s ease}
@keyframes fi{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.m-u{display:flex;justify-content:flex-end}
.m-u .bbl{background:var(--ac);color:#fff;padding:9px 14px;border-radius:var(--r) var(--r) 4px var(--r);max-width:72%;font-size:13.5px;line-height:1.6;white-space:pre-wrap;word-break:break-word}
.m-a .bbl{background:var(--s2);border:1px solid var(--bd);padding:12px 16px;border-radius:var(--r) var(--r) var(--r) 4px;font-size:13.5px;line-height:1.7;white-space:pre-wrap;word-break:break-word}

.tls{display:flex;flex-direction:column;gap:5px;margin-bottom:8px}
.tl{background:var(--s1);border:1px solid var(--bd);border-radius:10px;font-size:11px;font-family:var(--mono);overflow:hidden}
.tl-h{padding:7px 10px;display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none}
.tl-h:hover{background:var(--s2)}
.tl-d{width:6px;height:6px;border-radius:50%;background:var(--gn);flex-shrink:0}
.tl-n{color:var(--gn);font-weight:500}
.tl-p{color:var(--t3);margin-left:auto;font-size:10px;max-width:45%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tl-c{color:var(--t3);font-size:9px;transition:transform .15s}
.tl.open .tl-c{transform:rotate(90deg)}
.tl-b{display:none;padding:0 10px 8px;border-top:1px solid var(--bd)}
.tl.open .tl-b{display:block;padding-top:8px}
.tl-l{font-size:9px;text-transform:uppercase;letter-spacing:.8px;color:var(--t3);margin-bottom:3px}
.tl-o{color:var(--og);background:var(--ogg);padding:6px 8px;border-radius:6px;max-height:140px;overflow-y:auto;white-space:pre-wrap;word-break:break-word;margin-top:4px}

.ld{display:flex;align-items:center;gap:8px;padding:10px 0;color:var(--t2);font-size:12px}
.dp{display:flex;gap:3px}
.dp span{width:5px;height:5px;background:var(--ac);border-radius:50%;animation:pp 1.4s infinite}
.dp span:nth-child(2){animation-delay:.2s}
.dp span:nth-child(3){animation-delay:.4s}
@keyframes pp{0%,80%,100%{opacity:.15;transform:scale(.7)}40%{opacity:1;transform:scale(1)}}

.iw{padding:10px 12px 18px;flex-shrink:0}
.ib{display:flex;align-items:center;gap:8px;background:var(--s2);border:1px solid var(--bd);border-radius:12px;padding:5px 5px 5px 16px;transition:.2s}
.ib:focus-within{border-color:var(--ac);box-shadow:0 0 0 3px var(--acg)}
.ib input{flex:1;background:none;border:none;color:var(--t1);font-size:13.5px;font-family:var(--sans);outline:none;padding:7px 0}
.ib input::placeholder{color:var(--t3)}
.sb-btn{width:36px;height:36px;background:var(--ac);border:none;border-radius:9px;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:.15s;flex-shrink:0}
.sb-btn:hover{background:var(--ac2);transform:scale(1.05)}
.sb-btn:disabled{opacity:.35;cursor:not-allowed;transform:none}
.sb-btn svg{width:16px;height:16px}

::-webkit-scrollbar{width:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--bd);border-radius:2px}
</style>
</head>
<body>

<!-- Sidebar -->
<div class="sb">
  <div class="sb-h">
    <div class="sb-logo">水</div>
    <div class="sb-title">小水</div>
  </div>
  <button class="new-btn" onclick="newChat()">+ 新对话</button>
  <div class="chats" id="chats"></div>
</div>

<!-- Main -->
<div class="main">
  <header>
    <div class="hdr-title" id="curTitle">未选择对话</div>
    <div class="hdr-btns">
      <button class="hdr-btn" onclick="cmd('/tasks')">📋 任务</button>
      <button class="hdr-btn" onclick="cmd('/team')">👥 团队</button>
      <button class="hdr-btn" onclick="cmd('/inbox')">📬 收件箱</button>
    </div>
  </header>

  <div class="wrap"><div class="container">
    <div id="msgs">
      <div class="hi" id="hi">
        <div>
          <div class="hi-icon">💧</div>
          <h2>Hi，我是小水</h2>
          <p>你的个人编程助手。<br>点左上角「+ 新对话」开始聊天。</p>
          <div class="hints">
            <div class="ht" onclick="q('帮我看看当前项目结构')">📁 项目结构</div>
            <div class="ht" onclick="q('帮我列一个计划来重构这个项目')">📝 制定计划</div>
            <div class="ht" onclick="q('创建一个任务：写单元测试')">📋 创建任务</div>
            <div class="ht" onclick="q('派一个子agent去调研 README.md 的内容')">🤖 派子agent</div>
          </div>
        </div>
      </div>
    </div>
    <div class="iw"><div class="ib">
      <input id="inp" placeholder="跟小水说..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();go()}">
      <label class="sb-btn" style="background:var(--s2);margin-right:4px" title="上传文件">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <input type="file" id="upl" style="display:none" onchange="upload(this.files)">
      </label>
      <button class="sb-btn" id="btn" onclick="go()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
    </div></div>
  </div></div>
</div>

<script>
let curSid = null;

async function loadChats() {
  const r = await fetch("/api/chats");
  const chats = await r.json();
  const list = document.getElementById("chats");
  if (chats.length === 0) {
    list.innerHTML = '<div class="empty">暂无对话</div>';
    return;
  }
  list.innerHTML = chats.map(c =>
    `<div class="chat-item ${c.sid === curSid ? 'active' : ''}" onclick="switchChat('${c.sid}')">
      <span class="chat-item-title">${E(c.title)}</span>
      <span class="chat-del" onclick="event.stopPropagation();delChat('${c.sid}')">✕</span>
    </div>`
  ).join('');
}

async function newChat() {
  const r = await fetch("/api/new", {method: "POST"});
  const d = await r.json();
  curSid = d.sid;
  document.getElementById("curTitle").textContent = "新对话";
  document.getElementById("msgs").innerHTML = '<div class="hi" id="hi"><div><div class="hi-icon">💧</div><h2>Hi，我是小水</h2><p>你的个人编程助手。</p><div class="hints"><div class="ht" onclick="q(\'帮我看看当前项目结构\')">📁 项目结构</div><div class="ht" onclick="q(\'帮我列一个计划来重构这个项目\')">📝 制定计划</div><div class="ht" onclick="q(\'创建一个任务：写单元测试\')">📋 创建任务</div><div class="ht" onclick="q(\'派一个子agent去调研 README.md 的内容\')">🤖 派子agent</div></div></div></div>';
  loadChats();
  document.getElementById("inp").focus();
}

async function switchChat(sid) {
  curSid = sid;
  const r = await fetch("/api/chat/" + sid);
  const d = await r.json();
  const c = document.getElementById("msgs");
  c.innerHTML = '';
  const chatsR = await fetch("/api/chats");
  const chats = await chatsR.json();
  const me = chats.find(x => x.sid === sid);
  document.getElementById("curTitle").textContent = me ? me.title : "对话";
  d.messages.forEach(m => {
    if (m.role === "user") aU(m.text);
    else aB(m.text, []);
  });
  loadChats();
}

async function delChat(sid) {
  if (!confirm("确定删除这个对话？")) return;
  await fetch("/api/delete", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({sid})});
  if (curSid === sid) {
    curSid = null;
    document.getElementById("curTitle").textContent = "未选择对话";
    document.getElementById("msgs").innerHTML = '<div class="hi"><div><div class="hi-icon">💧</div><h2>Hi，我是小水</h2><p>点左上角「+ 新对话」开始</p></div></div>';
  }
  loadChats();
}

function q(t) { document.getElementById("inp").value = t; go(); }
function cmd(c) { q(c); }

async function go() {
  const inp = document.getElementById("inp"), t = inp.value.trim();
  if (!t) return;
  if (!curSid) { await newChat(); }
  const hi = document.getElementById("hi");
  if (hi) hi.remove();
  inp.value = "";
  aU(t);
  ld(true);
  try {
    const r = await fetch("/api/chat", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({msg: t, sid: curSid})});
    const d = await r.json();
    ld(false);
    aB(d.text, d.tool_calls);
    loadChats();
  } catch (e) {
    ld(false);
    aB("连接出错: " + e.message, []);
  }
}

function aU(t) {
  const c = document.getElementById("msgs"), d = document.createElement("div");
  d.className = "m m-u";
  d.innerHTML = '<div class="bbl">' + E(t) + '</div>';
  c.appendChild(d); c.scrollTop = c.scrollHeight;
}

function aB(t, tl) {
  const c = document.getElementById("msgs"), d = document.createElement("div");
  d.className = "m m-a"; let h = "";
  if (tl && tl.length) {
    h += '<div class="tls">';
    tl.forEach((x, i) => {
      const id = "t" + Date.now() + "_" + i;
      h += '<div class="tl" id="' + id + '"><div class="tl-h" onclick="document.getElementById(\'' + id + '\').classList.toggle(\'open\')"><div class="tl-d"></div><span class="tl-n">' + E(x.tool) + '</span><span class="tl-p">' + E(x.input) + '</span><span class="tl-c">▶</span></div><div class="tl-b"><div class="tl-l">输出</div><div class="tl-o">' + E(x.output) + '</div></div></div>';
    });
    h += '</div>';
  }
  if (t) h += '<div class="bbl">' + E(t) + '</div>';
  d.innerHTML = h;
  c.appendChild(d); c.scrollTop = c.scrollHeight;
}

function ld(v) {
  document.getElementById("btn").disabled = v;
  const c = document.getElementById("msgs"), l = document.getElementById("ldr");
  if (v && !l) {
    const d = document.createElement("div");
    d.id = "ldr"; d.className = "ld";
    d.innerHTML = '<div class="dp"><span></span><span></span><span></span></div>小水思考中...';
    c.appendChild(d); c.scrollTop = c.scrollHeight;
  } else if (!v && l) l.remove();
}

function E(s) { return s ? s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") : ""; }

loadChats();
document.getElementById("inp").focus();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    print(f"\n💧 小水对话版已启动: http://localhost:8002")
    print(f"📂 工作目录: {agent.WORKDIR}")
    print(f"💬 已加载 {len(chat_meta)} 个历史对话")
    print(f"🔧 工具数量: {len(agent.TOOLS)}\n")
    uvicorn.run(app, host="0.0.0.0", port=8002)
