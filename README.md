# RecallDock · 有证据的AI知识库

**v0.2.4 可运行功能版**。默认只允许本机访问。

## 已实现

- TXT/Markdown/PDF提取、页级来源、分块去重与SQLite持久索引
- BM25与离线词项向量融合；可选远程Embedding语义索引、模型隔离与并发修改拒绝
- 注册登录、多知识库、所有者/编辑/只读成员；检索和文档操作前校验权限
- 持久摄取队列、取消重试、重启恢复、文档更新、旧版原文查看和索引重建
- 问题历史与来源快照、追问上文、反馈、操作记录、知识库备份与校验恢复
- AI上下文预览、来源变化检测、真实服务端SSE增量、完成引用校验；离线检索无需Key
- 可选本地Tesseract OCR适配，页面配置API/模型/Key/Embedding模型
- 后台摄取任务显示持久化阶段、百分比、字节预算和片段计数；重启后可继续观察任务状态

## 运行

文档管理 → “移入回收站”只停止新检索，不永久删除正文/索引/版本。打开“文档回收站”可分页查看并恢复；写操作需要所有者或编辑权限。重复导入同一已移入的文件会409提示主动恢复，不会偷偷复活。没有自动过期、清空或永久删除入口。

Python 3.12，Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8768
```

打开 http://127.0.0.1:8768 。已有依赖时可用 `run.cmd`。其他系统使用 `.venv/bin/python`。`APP_DATA_DIR`覆盖数据目录。

## 可选AI

页面“API设置”填写兼容地址、模型与Key，Key仅在服务端内存保存，重启后使用环境变量。也可设置 `LLM_API_KEY`、`LLM_MODEL`、`LLM_BASE_URL`；不自动读取.env。不要提交或截图密钥。AI操作需用户主动触发，按服务商计费。本轮没有使用付费API。

语义检索设置 `EMBEDDING_MODEL` 后，在“语义索引”预览并确认发送原文；查询勾选远程语义时会发送问题。OCR设置 `OCR_ENABLED=1`、`TESSERACT_PATH` 和 `OCR_LANG`（如chi_sim+eng）。

## 数据与备份

数据位于data/，已排除Git；不要提交数据库、导入内容、磁盘清单或密钥。详细启动、备份和部署边界见 [运行说明](docs/OPERATIONS.md)。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app tests tools
python tools/evaluate.py
node --test tools/test-document-pages.mjs tools/test-version-pages.mjs
```

58项Python回归本地通过，另12项Node实际界面处理器测试覆盖当前及历史原文分页、乱序响应、关闭/切库、版本变化、重开与转义。Python含完整尾部、旧API兼容、每页权限撤销、回收站拒绝、参数边界、损坏快照、并发单读快照及Python仅解码请求的历史片段。远程Embedding和模型用mock，未调用付费API。测试初始化强制临时APP_DATA_DIR，不打开已有data/；所有前端脚本另做Node语法检查。跨平台结果以当前提交CI为准。

合成演示：`python tools/trash_demo.py`，临时书库与8895回环服务，回车停止/清理；不访问已有8768库。`python tools/trash_benchmark.py`只创建合成50000条文档metadata，报告尾页TestClient计时和Python allocation，不加载真实文档、不代表吞吐/SLA。

## 已知边界

- 回收站不是安全擦除。正文、索引、版本及历史问答的来源快照仍存本机；之前已经发送给模型的资料不能收回，已在进行的请求可能按它开始时的证据快照完成。UI当前生成时要求先停止/完成才能移入，但这不是跨客户端并发取消保证。
- 旧v0.2的DELETE为永久删除且无法从本版本凭空恢复。升级需先完整备份/停服务，不同时运行旧进程（旧查询忽略deleted_at，仍可检索trash）；本轮没有重启或迁移用户正在运行的服务。
- JSON备份version=1新增deleted_at并包含回收站文档，旧缺字段按active导入；旧客户端忽略字段会恢复为active。恢复仅导入当前片段/重建索引，仍不包含旧文档版本、消息、用户授权或远程向量；重复digest跳过，不改变既有文档状态。全APP_DATA_DIR停机备份用于完整恢复。
- 当前原文UI每页20片段，可前后翻页并显示版本/总数；新`GET /api/documents/{id}/chunks/page`提供offset、limit（1–50）、kb_id和expected_version。后续页版本变化返回409，清空旧页并要求明确重新读取；每次请求权限、metadata、count和片段来自同一SQLite读快照，响应no-store。旧`/chunks`保留列表/最多50项兼容。摄取任务面板显示持久化阶段、进度、字节数和片段计数。不是跨请求冻结快照，也不抵抗本机恶意写库者；大文档配额与回收站原文预览未完成。回收站metadata分页在并发变更时仍可移动。

- “版本历史”选择旧版本后每页20片段、前后翻页显示总数与版本；`GET /api/ingest/documents/{id}/versions/{version}/page`支持offset（0–2147483647）、limit（1–50）和kb_id，no-store。每次请求在同一读事务内复验active文档、当前知识库权限和历史版本；撤权/回收站后新请求拒绝，已开始的读快照可能完成，不承诺跨客户端安全擦除。关闭/Escape/切库/切版本丢弃迟到响应，不在当前检索中混入旧版。旧JSON和全量历史API保留兼容、无迁移；SQLite JSON1遍历旧数组，只将该页片段交给Python解码，但SQLite仍解析完整快照，COUNT/深OFFSET有成本，版本列表未分页。不是流式存储、硬CPU/RSS限制、取消传播或生产大文档吞吐承诺。

原文合成演示：`python tools/pages_demo.py`使用临时目录及8899回环服务，回车正常停止/清理，不打开已有8768。可选实际Chrome回归：安装独立测试用Playwright后`node tools/browser-pages.mjs`，仅针对该合成演示；也支持PLAYWRIGHT_MODULE指向已有隔离安装，无需更改运行依赖。

历史分页合成演示：`python tools/pages_demo.py --history`，在同类临时库将56片段原创长文保留为v1、再修订两次。点击“文档管理 → 版本历史 → 查看历史版本1”，可验证20+20+16及尾部；回车停止清理，不改变原服务或私人文档。

- 默认词项特征向量不是语义语言模型；远程Embedding需自配模型、API Key与额度。
- 流式内容生成中尚未校验；最终引用无效或连接中断不保存为成功回答。有效编号不保证事实正确。
- 追问仅继承最多3个上文问题并重新检索当前证据，不把旧回答当事实；来源保留文档版本。
- OCR需外部Tesseract及语言包，本机未安装，因此只验证缺失依赖行为；真实OCR效果未验收。
- 检索向量用SQLite全量扫描，上限10000片段；暂无ANN索引、本地语义模型和模型重排序。
- 五题合成评测Recall@3=1.0仅验证流程，不能代表公开领域泛化性能；授权公开语料评测待补。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。

[架构设计](docs/DESIGN.md) · [路线图](docs/ROADMAP.md) · [验收记录](docs/PROGRESS.md)

MIT License。用户导入内容不随源码发布。

使用体验修正：常见TXT编码自动处理、生成停止入口、流中断状态清理与手机对话框适配已接入。真实模型调用仍需自配Key并验收。
