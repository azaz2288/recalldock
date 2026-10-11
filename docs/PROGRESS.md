# 开发记录

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
