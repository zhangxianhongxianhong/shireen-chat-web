# Shireen Chat Web

基于 **Vue 3 + FastAPI** 的对话网站，后端支持 **通义千问** 与 **Dify** 双 Provider 切换，API Key 仅存服务端，可部署到 Vercel。

## 架构说明

| 层级 | 技术 | 作用 |
|------|------|------|
| 前端 | Vue 3 + Vite | 聊天 UI，SSE 流式展示 |
| 后端 | FastAPI | 代理千问 / Dify，隐藏 API Key |
| 部署 | Vercel | 静态前端 + Python Serverless |

## 切换 Provider

在 `.env` 中修改 `CHAT_PROVIDER` 即可：

```bash
# 使用通义千问（默认）
CHAT_PROVIDER=qwen
QWEN_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_API_KEY=sk-your-key
QWEN_MODEL=qwen-plus

# 切回 Dify
CHAT_PROVIDER=dify
DIFY_API_KEY=app-your-key
```

修改后重启后端生效。

## 本地开发

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 QWEN_API_KEY 或 DIFY_API_KEY
```

### 2. 启动后端

```bash
cd /Users/shireen/Project/dify-chat-web
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

## 部署到 Vercel

### 方式一：Vercel CLI

```bash
cd /Users/shireen/Project/dify-chat-web
npx vercel
```

### 方式二：Git 连接

1. 将项目推送到 GitHub
2. 在 [Vercel Dashboard](https://vercel.com) 导入仓库
3. 在 **Settings → Environment Variables** 添加：
   - `CHAT_PROVIDER` = `qwen` 或 `dify`
   - `QWEN_API_KEY` / `DIFY_API_KEY` 等对应变量

### 注意事项

- Hobby 计划函数最长执行 **60 秒**（已在 `vercel.json` 配置 `maxDuration: 60`）
- Pro 计划可设置更长时间
- 流式响应依赖 `X-Accel-Buffering: no` 头，已在后端配置

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/chat` | POST | 流式对话（代理千问或 Dify） |

请求体示例：

```json
{
  "query": "你好",
  "conversation_id": "",
  "user": "user-abc",
  "inputs": {},
  "files": []
}
```
