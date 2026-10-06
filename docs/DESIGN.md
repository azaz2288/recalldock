# 架构设计 · v0.2.1

retrieval.py维护中英文词项、BM25和词项特征融合；semantic.py处理显式远程向量调用并在提交前比较原文快照。workspace.py处理知识库权限和历史来源快照；ingest.py管理持久队列及事务版本更新；backup.py重建恢复索引；ocr.py本地渲染并调用Tesseract。main.py在检索前鉴权，完成回答后校验引用；llm.py提供普通和SSE兼容接口。

## 模块和边界

FastAPI + SQLite + 无构建原生Web UI。数据库外部调用不放入长写事务；默认Host/Origin校验、CSP和输入转义。

## 文档生命周期

trash.py additive迁移documents.deleted_at默认0和kb/time/id索引；旧数据仍active。DELETE成为幂等soft trash，显式POST /api/trash/{id}/restore恢复、active重复恢复409。事务内重查当前owner/editor、防撤权竞态，状态与audit同事务，不物理删除chunk/term/localvector/semanticvector/oldversion；没有purge/autoexpire。GET /api/trash鉴权且仅metadata，limit1–100、默认50，count/page单读snapshot、按deleted_at DESC/id排序。分页跨请求不是冻结快照。

active列表/正文/版本API与BM25计数/均长/df/candidates、semantic query/index/preview、reindex都排除trash。普通retrieve以BEGIN单读snapshot获取一致统计与来源。已完成问答及进行中的证据快照不回写删除；不声称跨客户端撤回模型请求或擦除历史。revision在写事务二次检查deleted状态，trash文档不能更新；duplicate upload/queue给409或failed，需要明确恢复。

backup v1兼容新增deleted_at，完整预验证有限非负timestamp（bool/非object/NaN/inf/巨大整数拒绝），single transaction重建片段并恢复trash状态；无字段旧版active。重复digest仅skip不复活；该JSON仍不备份版本、消息、账号权限或远程向量（用完整数据目录停机备份），旧客户端忽略字段会active化。旧服务v0.2不知道deleted_at不能并行运行，需升级前备份/停机；维护不改用户服务。

trash.js在现有refresh之后绑定可恢复操作与dialog20项分页，clear当前来源与预览fingerprint；切库丢陈旧列表/关闭，生成中不允许生命周期UI操作。history保留快照并提示不是安全擦除。范围只此纵向阶段，分页片段/任务进度/大文件配额仍未实现。

- 默认词项特征向量不是语义语言模型；远程Embedding需自配模型、API Key与额度。
- 流式内容生成中尚未校验；最终引用无效或连接中断不保存为成功回答。有效编号不保证事实正确。
- 追问仅继承最多3个上文问题并重新检索当前证据，不把旧回答当事实；来源保留文档版本。
- OCR需外部Tesseract及语言包，本机未安装，因此只验证缺失依赖行为；真实OCR效果未验收。
- 检索向量用SQLite全量扫描，上限10000片段；暂无ANN索引、本地语义模型和模型重排序。
- 五题合成评测Recall@3=1.0仅验证流程，不能代表公开领域泛化性能；授权公开语料评测待补。
- 默认回环访问，访客local是本机共享空间；账户可隔离内容，但不是公网多租户安全承诺。Cookie为本机HTTP设置，公网需TLS、安全Cookie、关闭访客、限流与部署审计。
