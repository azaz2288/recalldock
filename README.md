# RecallDock · 有证据的AI知识库

导入TXT、Markdown、文本型PDF，离线检索证据片段并定位出处。配置API后，模型基于检索片段回答并提供可核查引用。

**状态：v0.1 可运行基础版，按路线图持续开发。默认只允许本机访问。**

## 已实现

- 限额文件导入、中文编码处理、文本PDF分页提取与去重
- 保留页码/片段编号的重叠分块与SQLite持久化
- 中英文词项检索与TF-IDF风格评分，无密钥也可使用
- 可选模型问答，仅发送问题与命中片段，明确引用和证据不足
- 文档列表、预览检索上下文、删除文档、持久化索引

## 运行

需要 Python 3.12。Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8768
```

浏览器打开 http://127.0.0.1:8768 。其他系统用 `.venv/bin/python`；已安装依赖可直接运行 `run.cmd`。配置 `APP_DATA_DIR` 可改变数据目录。

## 数据

data/app.db 含导入文本、chunk、词项索引；原文件不另存。PDF图片和复杂表格没有完整还原。

## 可选模型配置

在启动服务器的 PowerShell 中设置环境变量（不会自动读取 .env 文件）：

```powershell
$env:LLM_API_KEY = "你的密钥"
$env:LLM_MODEL = "服务商支持的模型名称"
$env:LLM_BASE_URL = "https://api.openai.com/v1"
```

密钥只在服务端读取；不要写进前端、仓库或截图。接口为 OpenAI-compatible Chat Completions，可换兼容服务商。本项目不硬编码模型名称。AI 调用由用户主动触发，会按提供商计费；核心功能离线可用。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests
```

CI在Linux和Windows运行相同测试。实际执行证据见 [进度](docs/PROGRESS.md)。

## 已知边界

- 首版没有向量嵌入或重排序；属于词项检索，不能夸称语义检索
- 扫描PDF需OCR，第一版明确拒绝无法提取文本的文档
- 模型可能产生错误；仅接受当前上下文引用，仍需核对原文
- 仅单用户本地；没有多租户、权限隔离和公网服务
- API需要用户自配密钥、模型与额度，本轮不调用用户付费API

## 设计与后续

- [架构设计](docs/DESIGN.md)
- [按顺序开发的里程碑](docs/ROADMAP.md)

MIT License。用户导入内容不随源码发布。
