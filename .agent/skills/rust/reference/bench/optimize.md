# 只改一帧

目的：把读图结论变成最小补丁。写不出 Patch 就不要改文件。授权规则同 `bench`：裸调用只读。

## Patch（本命令专用四字段 + 全局表）

| 字段 | 必须 |
|---|---|
| `frame` | 点名的 self 符号 |
| `files` | 冻结范围内、真正拥有该调用的文件 |
| `refused` | 至少一条捷径（见下） |
| `retest` | 与采集**完全相同**的命令 |

全局字段仍按 [kernel/write.md](../../kernel/write.md)：intent、owner_layer、invariant、verification。

## 按热点分类改（PERF-02 次序）

| self 落在 | 先做 | 不要 |
|---|---|---|
| 你的算法 / 二次扫描 | 换结构或一次遍历 | 先 rayon |
| `clone` / `to_vec` / `collect` 再扫 | 借用或 `clone_from` | 为省 clone 拧 API |
| `Regex::new` / 重复 parse | `OnceLock` / 预编译 | 每次请求 new |
| allocator / `drop_in_place` | 少分配、复用缓冲 | 先 smallvec |
| 哈希 | 换 hasher 或免哈希路径 | 无数据换 FxHash |
| 正则引擎内部 | 缩小输入 / 锚点 | 改 crate 源码 |

## 拒绝落盘

- 无符号图上的「优化」。
- 一次改两帧或顺手 distill 整文件。
- `unsafe` 换速度（UNSAFE-05）除非用户点名且有 SAFETY。
- 引入 smallvec/ahash/rayon 而没有本帧证据。
- 为跑采样而 `sudo`。

## 验证

`retest` 必须墙钟数字，不是新图观感。噪声范围内如实「无显著变化」并回滚。
