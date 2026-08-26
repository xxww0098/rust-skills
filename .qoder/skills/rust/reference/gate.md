# /rust-skills:rust gate — 门禁生成与维护

目的：把**适合机器判定**的规则落成真实检查。按 META-01，规则默认是 review/eval；只有实现、失败 fixture 与注册三者齐全才升级为 machine gate，不要求所有规则伪装成自动化。裸调用只输出 ENABLED / NOT_IMPLEMENTED / REVIEW_ONLY 体检；`--apply` 或明确写入授权后才改入口、CI 或 hooks。

## 首次（项目无统一门禁）

1. 先盘点 Cargo alias、Makefile/justfile、CI、hooks、lint 与测试脚本。能在已有入口加一条命令就复用；只有多项自定义检查需要共享 Rust 逻辑时才生成零依赖 xtask。调用 alias 入口时：`cargo --manifest-path` **不能**驱动 `.cargo/config.toml` alias——须先 `cd` 到项目根，或用 `cargo run -p <xtask包> --manifest-path <根>/Cargo.toml -- …`。
2. 选定一个统一入口。每个注册检查必须满足：
   - 有与规则号的映射；
   - 有会失败的 fixture/测试；
   - 实现检测逻辑，不能用 TODO、固定 `Ok(())` 或注释桩冒充；
   - 实跑失败/成功样例后才列为 ENABLED。
3. 只实现当前项目确实需要且低误报的检查；通常先考虑 `no_orphan_modules`（TEST-04）、`no_wildcard_opt_level`（BUILD-01）、`no_test_code_in_lib`（TEST-05）、`no_silent_test_skip`（TEST-07）。项目自管子进程或跨 Windows 路径时，可用 clippy `disallowed-methods` 挡裸 `Command::spawn` / `canonicalize`（PR-03/XP-05），不引入新 crate。布局、依赖收口、doctest 和 publish 策略仅在项目已明确采用时门禁。
4. 未实现项列为 `NOT_IMPLEMENTED` 且不注册；若它属于用户要求的最低检查集，gate 必须非零退出，不能假绿。
5. 可选棘轮：用 `cargo clippy --message-format=json` 生成基线；记录命令、工具链和时间。基线下降就收紧；放宽或移除须给理由与补偿证据（GATE-02）。
6. hooks 只生成到版本化的项目路径（如 `scripts/hooks/`）并给安装说明。发现现有 `.git/hooks/*` 时绝不覆盖；只有用户明确同意安装后才写 Git 私有目录。
7. CI 变更先展示计划；用户授权后复用同一门禁入口，不复制第二套规则。有 `Cargo.lock` 的应用：构建/测试必须 `--locked`；扫 workflow 里的 `cargo update`（DEP-11/GATE-04）。冷却期不是默认基线：只在 artifact=service|cli|desktop 且用户要供应链闸时，把 RFC 3923 配进 `.cargo/config.toml`，并用 **G4 nightly** `cargo +nightly -Zmin-publish-age check --locked` 验证解析；默认 toolchain 仍是 stable。

```toml
# 应用侧候选（实验性；稳定前仅 G4 / 显式授权）
[registry]
global-min-publish-age = "14 days"

[registries.crates-io]
min-publish-age = "7 days"

[resolver]
incompatible-publish-age = "deny"
```

紧急热修（知情）：`CARGO_RESOLVER_INCOMPATIBLE_PUBLISH_AGE=allow cargo update -p foo --precise 1.2.3`，完后改回 deny。私有 registry 可 `min-publish-age = "0"`。无 `pubtime` 的 registry 静默跳过，须声明缺口。

## 增量（已有统一门禁）

- 新规则可机械判定 → 先补失败 fixture，再实现检查并注册；不可机械判定 → 保持 review/eval 清单，不塞假检查。
- 每次输出 `ENABLED`、`NOT_IMPLEMENTED`、`REVIEW_ONLY` 三张清单；只把 ENABLED 计入覆盖率。
- 检查耗时超预算 → 移到更慢阶梯；不得静默跳过或固定成功。
- 默认只输出 RUST.md 棘轮快照建议；只有显式 `--record` 才写 RUST.md。

## 输出与完成条件

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **只读体检**：统一入口、ENABLED / NOT_IMPLEMENTED / REVIEW_ONLY 三表、与 skill 候选集差距、实跑或「未重跑/从配置推断」声明。
- **写入授权后**：改入口/检查/CI/hooks 的计划与 diff；失败 fixture 与实跑证据。

完成条件（写入路径）：选定入口对坏 fixture 失败、对好 fixture 成功；任何必需项仍为桩时不得报告门禁完成。只读路径：三表齐全且未改文件即可。
