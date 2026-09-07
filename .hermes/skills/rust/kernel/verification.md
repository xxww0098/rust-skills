# kernel/verification — 只决定怎样证明修改正确

写完才读。禁止把 `eval-fixtures` 绿、或 `check_patch` 绿，当成「代码已规范」。

所有写入命令（harden / slim / cargo / test / distill / modernize / craft 叠加）只走一个入口：

`python3 <SKILL.md 所在目录>/scripts/verify_patch.py --patch <Patch.json> --root <项目根>`

该脚本必须跟 SKILL.md 一起被安装；只有源仓正文、没有 `scripts/verify_patch.py` 的副本不能声称可验证。

默认只分类，不跑 cargo。要执行 Patch.verification，必须显式 `--run`。`proven=true` 只在 cargo 实际退出码为 0 时出现。

## 最小闭环

1. **verify_patch**：先复用 `check_patch` 的 Patch 契约与生产形状扫描，再解析 `verification`。
2. **分类**（没 `--run`）：`gap` 未写命令；`invalid` 契约不全或不是单条 `cargo check|test|nextest`；`missing-manifest` 路径不存在；`runnable` 可以跑但还没跑。`runnable` ≠ 已验证。
3. **执行**（`--run`）：只允许 `shlex` 拆开的一条 cargo，必须带 `--manifest-path`，禁止 `&&` / `|` / 环境替换。成功才是 `ran` + `proven`。
4. **快照不漂**：同一 commit + 同一 target，`inspect_project.py` 的 members/edges/cycles/orphans/signals 字节一致。
5. **画像不漂**：`document` 的四个投影节必须来自 `python3 scripts/render_rust_md.py <根>`，禁止手绘 crate 图。

## 什么不算验证

- 压力场景文件存在、fixture 关键词还在（那是 E1/E2）。
- `check_patch` 绿但没有 `verify_patch` 报告，或报告里 `proven` 不是 true。
- 只跑了邻接 crate、没钉 `--manifest-path`。
- 对仓库根或 crate 目录跑了 `check_patch.py`，却没有 Patch JSON。
- Patch.files 以外的文件上的形状命中（那是审计，不是这次写入的证据）。
- 模型口播「已 cargo test」。
- 技能正文已安装，但 SKILL.md 旁边没有 `scripts/verify_patch.py`。
