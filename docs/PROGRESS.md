# 开发记录

## 2026-10-22 v0.2.4 旧版原文分页（America/New_York）

- 新历史/page端点同BEGIN读事务复验active文档/owner/member/kb/version，JSON1原序COUNT与LIMIT/OFFSET，20默认/1–50/offset有界、no-store；不重写旧JSON/迁移或破坏旧API。只在Python解码该页对象，SQLite仍需解析完整历史数组，不称硬资源策略完成。
- 先7新增方法在旧实现11fail/1error含参数subcase（page端点未实现/导入mock目标缺失），再实现后7通过；新增坏JSON/非数组409，共8新/58Python20.386s通过。涵盖56以上完整尾部与旧API等价、重启/再修订不变、每页撤权/trashed恢复、非法limit/offset/version、空页、Python仅页内解码、COUNT后并发trash仍返回同snapshot。原50方法保留；Starlette/httpx弃用警告非测试失败，未为此改项目环境。
- 新6+原6共12Node121.2845ms通过，执行实际shipped控制器：57片段全部可翻、immutable版本选择、切版本/文档乱序、关闭/Escape/切库、queued close重开、撤权/错误metadata清正文和禁导航、转义。CI与根巡检均纳入新测试。compile app/tests/tools、全部JS语法、pipcheck和五题合成检索评测通过，五题Recall@3=1.0只验证流程，不代表真实领域效果。
- Chrome156.0.8078.47独立临时8899合成库：真实56历史片段20+20+16和尾标记/上一页、v2独立正文、真实HTTP延迟v1切v2不覆盖、加载关闭迟到不复开、Escape重开、实际切库handler丢迟到通过。原生modal阻止背景物理交互，切库竞态用真实onchange程序触发，恢复时先物理回问答页再选库；不冒称模态背后点击可达。390×844 body390/dialog358、scroll=client356，console/pageerrors空；桌面/手机截图已视觉检查，正文/选择/前后页/关闭可读，无横溢出。首两次脚本因重复按钮strict selector、文档页知识库select隐藏而失败，属验收脚本定位/导航问题，修正后全通过。
- 完整提交SHA/同SHA双平台CI证据见根本日维护报告，未通过不借旧CI。新版本列表仍全量、SQLite JSON1非硬CPU/RSS沙箱、已开始的读snapshot仍可完成；不做模型API/OCR调用、不读私人库、不恢复旧Verisnap任务或补造中断历史。
- 追加超SQLite整数version与页内坏片段边界先复现1fail/3error（含子case），再限制version到1..2147483647、仅页内对象字段验证，返回422/409而非500/无效成功；不以恶意本机改库作为安全沙箱承诺。最终58/12以根发布报告为准。

## 2026-10-15 v0.2.3 摄取进度与容量可见性

- `ingest_jobs` 增加可向后兼容的 `progress`、`stage`、`bytes_total`、`items_done`、`items_total` 字段；入队、读取、准备、完成、取消和失败都更新持久状态。
- 摄取任务面板显示阶段、百分比、字节数和片段计数，避免长文档导入时只能看到 queued/running；重启后仍可读取最后状态。
- 新增合成大文本进度/字节预算回归；未引入真实用户资料、并行调度或硬CPU/RSS配额。

## 2026-10-12 v0.2.2 当前原文分页

- 新/page端点有限items+total/next_offset/version；单读快照内权限/active/计数/有序正文，expected_version不一致409，no-store，旧/chunks列表兼容。UI20项/前后页/重新读取/关闭与切库代次，失败清旧正文，当前title纯文本/content转义；修复queued close事件不能清重开的view。
- 6新增Python方法（43原有→49）与6Node actual shipped-handler测试通过：>50尾部独立SQL序列、空/越界/50边界/非法参数、trash/restart/restore、reader撤权、修订409、COUNT后并发revision仍返回同份旧snapshot；UI乱序/关闭/切库/版本/重开/错误metadata/转义。首旧实现9failure/3errors含subcases；fixture Proxy self遮蔽导致1error和Windows清理继发error，改捕获外层test后6target通过，不弱化snapshot验收。
- 完整49方法15.887s、Node6/125.7043ms、compile/JS/pipcheck/diff以及五题合成eval通过（Recall@3=1.0只是五题流程，不代表公开领域准确率）。浏览器和发布当前SHA证据见根每日报告；不调用付费模型/不打开已有知识库。
- cua/node_repl均初始化失败（系统路径不存在），reset后仍失败；改用独立headless Chrome/已有隔离Playwright实际测试。首次翻页断言通过但favicon404触发console严格失败，添加本地SVG favicon后全通过：56合成片段20+20+16/尾标记/上一页/关闭重开/切空库再返回；390×844 body390、dialog358/scroll=client356，console error/warn空。截图在根reports，真实手机未验；8899服务正常Enter停并清理，无listener、不碰旧服务。第一次demo非tty inputEOF立即停止，后用tty启动。
- 单页事务不是跨页冻结snapshot，恶意本机写库/深OFFSET与COUNT资源预算未保证；历史版本正文仍旧全量逻辑，导入进度/配额与其他路线未完成。未重启用户8768服务。

## 2026-10-07 v0.2.1 回收站阶段

- 旧DELETE不可恢复，新增softtrash/explicitrestore/metadata分页/原子审计，正文/索引/版本保留。新检索统计、词项及semantic、preview/reindex都过滤trash；重复文件普通/后台导入不复活，revision二次状态检查。
- 首12新测试修前12fail/2error含子case，不能当14独立漏洞；实现后pass。再扩fault/legacy/metadata/history/queue等合计17新，最终43方法通过。全43初次1error是mock共享time.time影响httpcookiejar，改局部module绑定后全过。tests/evaluate强制tempbootstrap，未打开用户资料。
- 合成8895实际检索三十天→移入noevidence→恢复三十天，23trash20+3分页，当前回答清除；390×844dialog358px、body/dialog无overflow，console error/warn空。临时视口恢复，真实手机未连接；没有付费provider/OCR调用。
- 50000合成metadata尾页offset49900/100条测量0.088741/0.043750/0.044355秒，Python allocation峰1031560/177050/162464B；第一个cold，无独立warmup，不计SQLite原生RSS、不是正文检索吞吐/生产SLA。旧五题BM25/hybrid Recall@3=1.0与拒答流程重验，不夸为公开领域准确率。
- compile app/tests/tools、pipcheck、Node全JS及根维护5通过。发布完整SHA/同SHACI证据写在本机maintenance；当前未通过不借父绿灯。分段预览/进度/大文档策略及其他未完项保留。
- 回收站/历史不是擦除，进行中证据快照不可收回；旧永久删除不可恢复。JSON恢复只当前片段、trash状态与重建索引，不含版本/消息/账户权限/远程向量；旧客户端会忽略状态，升级需停旧进程且备份。维护不重启用户8768/不读私人库。

## v0.1 验证

- 文本/PDF导入、页面分块、词项索引、检索证据、API上下文预览和引用校验实现。
- 独立venv的11项测试全部通过，含真实合成文本PDF、无文本PDF拒绝、删除级联、重启检索、无证据不调用模型、引用无效拒绝。
- 模型行为用mock验证；没有用户密钥，未做真实付费API连通性验证。
- Chromium导入中文手册、检索备份保留证据通过，桌面与390px移动布局无脚本错误或横向溢出。
- 当前为词项检索；向量、OCR、流式问答和权限仍在路线图。

- 初版GitHub公开发布完成，Windows/Linux同提交CI成功；完整SHA与CI链接保存在本地维护报告。所有用户数据目录与环境配置均排除在Git之外。

## 2026-10-06 v0.2 功能扩展

- TXT/Markdown/PDF提取、页级来源、分块去重与SQLite持久索引
- BM25与离线词项向量融合；可选远程Embedding语义索引、模型隔离与并发修改拒绝
- 注册登录、多知识库、所有者/编辑/只读成员；检索和文档操作前校验权限
- 持久摄取队列、取消重试、重启恢复、文档更新、旧版原文查看和索引重建
- 问题历史与来源快照、追问上文、反馈、操作记录、知识库备份与校验恢复
- AI上下文预览、来源变化检测、真实服务端SSE增量、完成引用校验；离线检索无需Key
- 可选本地Tesseract OCR适配，页面配置API/模型/Key/Embedding模型

24项全部通过，包含真实文本PDF、检索前权限过滤、摄取完成、版本保留、备份恢复重建、Embedding mock、索引并发修改拒绝、追问隐私、流式引用校验及预览变更拦截。模型使用mock，未调用付费API。

使用原创合成示例完成浏览器交互；未读取个人文件、未操作真实磁盘清理、未调用付费API。保留路线图中实际未完成项。

## 实际使用审查

TXT/Markdown沿用旧解码器的误报问题一并修正：加入UTF无BOM与Big5检测、稀疏NUL处理、二进制拒绝，全文件严格解码。生成开始清理旧来源与反馈ID，生成期间锁定知识库选择并提供停止入口；中断/校验失败明确显示未完成，不留下旧证据误导用户。AI生成关闭预览对话框以让停止入口可操作。对话框限制高度、长文件名和手机操作适配。26项回归全部通过，含新增文本导入用例；真实付费API和手机设备不在本轮验收范围。
