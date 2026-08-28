# kernel/verification — 只决定怎样证明修改正确

写完才读。禁止把 `eval-fixtures` 绿当成「代码已规范」。

## 最小闭环

1. **Patch.verification**：用户项目上跑 Patch 里写的那条 `cargo test`/`cargo check`。没跑就写缺口，不准说已验证。
2. **check_patch**：`python3 scripts/check_patch.py <Patch.files>`。命中 unwrap / println / dbg / `.clone()` / `&String` / `for i in 0..` → 补丁不合格，改到规范形状再交。
3. **快照不漂**：同一 commit + 同一 target，`inspect_project.py` 的 members/edges/cycles/orphans/signals 字节一致。
4. **画像不漂**：`document` 的四个投影节必须来自 `python3 scripts/render_rust_md.py <根>`，禁止手绘 crate 图。

## 什么不算验证

- 压力场景文件存在、fixture 关键词还在（那是 E1/E2）。
- `cargo check` 绿但 Patch 拒绝清单未跑。
- 只跑了邻接 crate、没钉 `--manifest-path`。
