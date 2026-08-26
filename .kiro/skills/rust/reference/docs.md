# /rust-skills:rust docs [target] — 治理文档集合

目的：治理仓库文档的可发现性、权威性、生命周期与引用完整性。`document` 只投影 RUST.md；本命令管理 docs 集合，不替 ADR/CONTEXT 做决策，也不评审公共 API rustdoc。默认只读；`--apply` 或同一请求明确“创建/整理/更新索引/修复链接/移动/归档”后才写。

## 步骤

1. **钉死两层根**：回显项目根与 docs 根。无 target 时取 `<项目根>/docs`；target 为 docs 目录、子目录或文件时以它为主目标并向上解析项目根。docs 不存在时只报告；明确要求创建后才写。
2. **冻结现状**：清点 docs 内已跟踪、未跟踪和资源文件，读取现有首页/站点配置；再找根 README、AGENTS/CONTRACT/PRODUCT/DESIGN、源码注释与脚本中的入链。单列 dirty 文件和所有权约束；不 stash、不覆盖并行修改。
3. **建立目录账**：除首页自身外，每个目标内容文档恰好一行，给出 `路径｜kind｜status｜authority｜evidence baseline｜入链｜问题`；图片、schema 等资源另列依赖。分类只采用正文声明、项目约定、可解析 Git 对象、后继文档与当前实现证据：
   - kind：`standard|decision|design|runbook|reference|audit|benchmark|report|archive|unknown`
   - status：`draft|active|accepted|superseded|historical|stale|inconclusive|unknown`
   - authority：`canonical|derived|snapshot|external|unknown`
   文件名、mtime、行数和目录深度不能单独决定分类；不强制批量添加 frontmatter。
4. **核对可寻址性**：检查本地相对链接、锚点、反引号路径、站点导航与 pinned revision 是否存在；外部 URL 未按用户要求联网时标 `UNVERIFIED`。这里验证证据能否找到，不重新证明整篇技术结论。把重复事实、竞争 SSOT、失效基线、孤儿文档和缺失 successor 分开列出。
5. **首页优先**：没有文档首页时先提议最小 `docs/README.md`，只做入口、分组和一行用途，不复述正文。现有扁平目录仍清晰时保留；只有多个文档形成稳定主题或生命周期边界、且全部入链可同步时才提议子目录。不给空 taxonomy，不按篇幅拆文档。
6. **分阶段写入**：只读调用输出当前树、目录账、目标树和 `旧路径 → 新路径 → 必改入链` 表，不落盘。写模式先回读 dirty 状态并展示精确写集；只执行用户明确授权且已展示的首页、状态提示、移动与必要入链更新，历史审计/基线/report 正文作为证据快照保留。移动所需入链未纳入写集或发生 dirty 冲突时保留旧路径。合并、删除、归档和选择权威源逐项确认。
7. **闭环**：复查首页之外的目标内容文档只被索引一次、相对链接与已迁移入链可达、旧路径无残留、dirty 文件字节未变。纯索引、Markdown 或注释路径变更只跑文档检查与 diff check；项目明确门禁要求或代码语义有变化时才叠加 Cargo 检查。报告无法验证的外部链接/历史 revision；相同状态复跑不产生 diff。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

输出 `项目根｜docs 根｜模式｜dirty 排除`、目录账、权威/生命周期冲突、当前树 → 目标树、移动与入链表、验证结果。没有写授权时给可执行的分阶段方案；写模式给实际 diff 摘要并区分已完成、保留和待确认。

完成条件：首页外的目标内容文档已分类或明确为 `unknown`，资源依赖已列出，每个权威/过时结论都有证据，零未报告断链；只读模式目标仓零写入；写模式不越过冻结清单、不覆盖 dirty 内容且复跑幂等。
