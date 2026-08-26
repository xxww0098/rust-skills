## ERR 错误处理
- ERR-01[M] 稳定库公共 API 返回调用方可处理的具名错误并保留 source 链；可用手写 `Error` 或 thiserror。只在接口契约允许不透明错误时返回 `Box<dyn Error>`。
- ERR-02[S] 应用编排层为错误补上下文；可用 anyhow，或项目已有的 eyre/miette/等价 Report。不为这一点单独强加依赖，也不把库 API 改成 anyhow。
- ERR-03[M] 生产禁裸 unwrap；expect 仅限局部可证明不可失败且消息写成证明 `expect("invariant: …")`；测试不限。
- ERR-04[M] panic 只代表 bug；可预期失败一律 Result；禁 panic/catch_unwind 做控制流。
- ERR-05[M] 禁 `let _ = fallible()` 吞错；要忽略须记录或注释论证。
- ERR-06[S] 公共错误 enum 加 #[non_exhaustive]；消息小写、无尾句号、不重复 source 内容。
- ERR-07[S] builder/guard/句柄类返回值标 #[must_use]。
- ERR-08[S] anyhow/thiserror 不是精简前提：先 `Result` + `?`。变体少且调用方不必 `match` → 手写 enum 或具体类型，不新加 crate。禁止为「看起来专业」在同一产物里同时引入两个；禁止把 anyhow/eyre 当库的公共错误类型。项目已有其一则沿用。
