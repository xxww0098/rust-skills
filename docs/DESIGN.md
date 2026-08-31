# rust-skills 设计文档

架构与维护约定，面向维护者。用户面见 [../README.md](../README.md)。

## 架构

- **SKILL.md 只做调度**：从用户动词判定读写授权（见 SKILL 的「写入边界」，按命令分类一条规则），再按需加载一个 playbook 和领域覆盖层。普通实现（未点名子命令）默认加载 `reference/craft.md`；Cargo 项目里的 Rust 轮次先加载 `reference/engage.md` 主动介入。二者与 `routing.md` 一样不进命令表。
- **一个画像投影器**：`document` 独占 RUST.md 画像投影；`init` 修改基线后复用它。投影节从 post-state 重算，其他命令的稳定键账本合并保留。
- **画像与文档分权**：`document` 管机器可重算的 RUST.md；`docs` 管人类文档集合的首页、权威源、生命周期和入链，不替 ADR 作决定。
- **状态在项目里，不在技能安装缓存里**：`init`/`document` 在项目根维护 `RUST.md`；`capture` 默认写项目内 `.rust-skills/capture-outbox.md`。已安装插件目录视为只读、可替换的运行时资源。
- **适用性先于编号**：每条发现都要给规则前提、代码证据和可观察后果；项目约定或反证可推翻 SHOULD。
- **正交画像**：每个 crate 分开记录 `artifact=lib|service|cli|desktop` 与 `maturity=prototype|production`，不拿仓库级标签覆盖所有成员。
- **框架深入子 playbook**：`reference/axum/`、`reference/tauri/` 与 `reference/seaorm/` 存放按信号加载的深入材料。owner `reference/axum.md` / `tauri.md` / `seaorm.md` 独占 AX/TA/SO 编号，写成薄索引（门条款保留短说明，其余一句话 + 深入表），子文件只能括号引用编号，不得定义。一致性脚本校验子目录的 owner 存在、每个子文件有 `目的：`、被 owner 入链、规则引用合法。新增子文件只需在 owner 表里加一行；新增编号只在 owner 追加并保持连续。SKILL 本轮预算：1 个命令 owner + 至多 2 个子 playbook + 至多 3 个 `rules/<domain>.md`，禁止整目录读 `reference/axum|tauri|seaorm|bench|slim/`。出处（已蒸馏完毕，源包不再随仓保留，需要复核时重新 clone）：`https://github.com/Impertio-Studio/Axum-Claude-Skill-Package` @ f5b0cd4、`https://github.com/full-stack-skills/tauri-skills` @ 17c7356。
- **doctor 自反**：库自己也是软件——编号一致性、命令表↔文件对应、写入边界分类、场景覆盖、**每个命令的磁盘 fixture**、**version floor** 都有体检。一致性脚本必须在 `LC_ALL=C` 下也能跑（UTF-8 场景标题含全角括号）；优先本机/CI 的 `rg`（ripgrep），`rg` 垫片不得把缺文件吞成空匹配。有磁盘 fixture 的场景由 `scripts/eval-fixtures.py` 读 `tests/fixtures/scene-*/contract.json` 做机械契约，不是 LLM 会话替代品。`scripts/check-floor.py` 钉死 axum/tauri/sqlx/sea-orm 现行线和 edition/MSRV；`--fetch` 才打 crates.io。
- **命令级 swarm**：`kernel/swarm.md` 是编排表不是命令。多文件探索可并行只读车道，合并进同一份 ProjectSnapshot。`craft`/`triage`/`shape`/`capture`/`init` 与火焰图改帧循环禁止扇出。子 agent 不写文件。

## 命令表单一事实源

`scripts/command-metadata.json` 是命令的用户面事实（分类/一句话/参数提示/中英触发词）单一来源；`scripts/gen-command-tables.py` 生成 SKILL.md 路由表与 README 命令速查。新增/改名命令：改 metadata + reference + 压力场景 + 磁盘 fixture，跑 `./scripts/gen-command-tables.py` 与 `./scripts/check-consistency.sh`。

## 规则治理

`skills/rust/rules/<domain>.md` 是分级规则的按域源；`rules/rules-full.md` 由 `scripts/gen-rules-full.py` 合并，只给全规范审计和一层扫描器。6 个 D-* 决策树和各框架局部清单不计入该数字。M 只在规则前提命中后阻断，S 可被项目约定或证据推翻。新增规则必须声明是机器门禁还是评审清单项，并补相应验证（META-01/03）。技能仓以命令级压力场景 + `./scripts/check-consistency.sh` 为准；machine gate fixture 只在用户项目落地 `gate` 后计算。2024 链接属性、`unsafe extern` 与 Unix `set_var` 按 Edition Guide / std Safety 写进全局规则，不靠 folklore。

## 发布与同步

- **安装入口是 SkillStar**，不是再做一套 impeccable 式的自安装器。用户侧：`skillstar add xxww0098/rust-skills`。安装单元是某一个 `.<harness>/` 层（或其中的 `skills/rust`），不是整仓。仓库根不再放 `SKILL.md`；SkillStar 不得把 clone 根当成一条技能。
- 插件和规范都从 `0.0.1` 起按补丁递增。权威文件是 `.claude-plugin/plugin.json`；改完后跑 `./scripts/sync-providers.py`，它会先重生成命令表与 `rules-full.md`，再写各 harness 清单、**独立副本**（不是出仓即断的相对 symlink）和 `skills/rust/SKILL.md` / `rules/preamble.md` 的版本。不要手改 `.<harness>/` 里的投影。没有 SkillStar 时，这些副本和 Claude/Grok/Cursor 插件仍是后备安装路径。
- 技能正文只维护 `skills/rust/`。Git 安装单元是某一个 `.<harness>/` 层（或它里面的 `skills/rust`），不是整仓。仓库根不再放 `SKILL.md` / `reference/` / `rules/` 兼容垫片——那会让扫描器把 clone 当一条技能，把 `tests/`、`scripts/`、其它 harness 一并装进去。一层扫描器请装 `.dsh/`（或对应 harness），不要把 clone 根当技能目录。
- 当前修正版已用 Claude Code CLI 2.1.233 验证；尚未声明更早版本的兼容下限。

## 生长节奏

当场：踩坑/三振/被打回 → `/rust-skills:rust capture`，先进入项目 outbox；人工确认后才在技能源码仓库提升为规则与压力场景。每周：跑一遍 `tests/pressure-scenarios.md` 与 `./scripts/check-consistency.sh`（含 fixture eval）；`/rust-skills:rust doctor` 看漂移。不为本 skill 新开命令——缺的是 2024 之后会写错的语义。
