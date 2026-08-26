# /rust-skills:rust triage [error] — 编译错误分诊

目的：把编译错误当成**症状**，先追溯领域约束再给方案（D-6 + 三振 + OWN-01）。无参数 → 跑 `cargo check --workspace 2>&1` 取当前错误集。**任何 Rust 会话中出现编译错误都自动适用本纪律，不必等用户敲命令。** 本命令永远只读：输出追溯链与对照表，`--apply` 不适用。同一请求明确「修/改/实现」时叠加 [craft.md](craft.md) 才写码。

不要停在机制层给 `.clone()`。这是 actionbook/rust-skills 元认知里唯一值得收的部分：错误从 HOW 向上问 WHY，再向下选 WHAT。

## 三层与追溯方向

```
领域 WHY（L3）  这份数据在业务里是什么？不可变事实 / 可变工作副本 / 临时缓冲？
      ↕
设计 WHAT（L2） 共享（Arc/&）还是独立副本（clone）还是拆类型？
      ↕
机制 HOW（L1）  E0382 / E0597 / E0277 … 编译器在挡哪条规则？
```

| 信号 | 入口 | 方向 |
|---|---|---|
| E0xxx / rustc / borrow checker | 机制 L1 | **必须向上**问领域，再向下给设计；禁止只答 HOW |
| 「这个功能怎么建」 | 领域 L3 | 向下：约束 → 模式 → 机制（走 [shape.md](shape.md)） |
| 同一处三振 | 机制 | 升级到设计/领域，停局部修补 |

领域信号从**用户用词和标识符**取（`audit`/`ledger`/`TradeRecord`/`invoice`）；没有信号就问一句「这份数据的业务角色？」，**不要发明监管/合规要求**。

## Error → Design Question（先答右列，禁止直接做中列）

| 错误 | 条件反射（禁） | 先回答 |
|---|---|---|
| E0382/E0507 moved | 加 `.clone()` | 谁该拥有这数据？共享不可变→`&T`/`Arc`；确需独立演化的副本才 clone 并说明 |
| E0597/E0515/E0716 生命周期 | 加 `'static` | 作用域边界画对了吗？该返回所有权吗？ |
| E0499/E0502 双借用 | 套 `RefCell` | 数据该拆分吗？突变点该移走吗？重构无果才内部可变性 |
| E0506 assign while borrowed | 硬挪一行 | 读写阶段能分开吗？ |
| E0277 Send/Sync | `Rc`→`Arc` 了事 | 这类型**该**跨线程吗？共享模型选对了吗？ |
| E0277 trait bound | 盲加 bound | 这个边界表达什么能力需求？该收窄类型吗？ |
| E0308/E0599 | 强转/to_owned | 类型建模表达意图了吗？缺导入还是缺设计？ |
| 2024 RPIT 捕获了不该捕获的生命周期 | 一律 `+ 'static` 或随手写 `use<>` | edition 2024 在无 `use<..>` 时捕获全部 in-scope 泛型。返回类型该不该拥有数据？要少捕获才用 `use<…>` |
| `if let` 临时值在进 else 前被 drop（2024） | 「退回 2021」或到处 `let _keep` | 需要临时值活过整个 if/else 时改写成 `match`。短作用域是 2024 预期行为 |
| `unsafe fn` 体内裸 unsafe 操作（2024 `unsafe_op_in_unsafe_fn`） | 给整函数 `#[allow(unsafe_op_in_unsafe_fn)]` | 函数标 `unsafe` 只声明调用约定。体内每个 unsafe 操作仍要 `unsafe {}` + SAFETY（UNSAFE-03） |
| `!` fallback / `never_type_fallback_flowing_into_unsafe` | 退回 2021 或到处 turbofish | 2024 的 `!` 不再默默变成 `()`。`f()?`、闭包 `panic!()`、if/else 一臂 `return` 要对 Ok/返回类型写 `()` 或具体类型；`!` 不得流进 unsafe |

回答完，clone/RefCell/Arc 可以是正确答案——区别在于它是结论不是反射。推荐 clone 或 Arc 时必须填下面对照表。

| 方案 | 成本 | 语义 | 仅当领域是… |
|---|---|---|---|
| `&T` | 零 | 借用，不延长寿命 | 调用方能活过这次使用 |
| `Arc<T>` | 原子计数 | **同一份**不可变事实 | 多处要同一记录且不该分叉（审计/账本） |
| `.clone()` | 深拷贝 | **独立副本**，此后可分叉 | 两处必须独立演化；须注释「为何两处都要所有权」（OWN-01） |

## 强制输出：追溯链（不得省略）

```
机制 HOW：E0382 = 值 move 后再用 → 为什么两处都要这份数据？
领域 WHY：<业务角色，来自标识符或用户一句> → 共享事实还是独立副本？
设计 WHAT：Arc<…> / & / 有意 clone —— 领域约束决定答案，不是编译器
```

交易系统示例（用户说「trading / 审计 / ledger」时）：

```
机制 HOW：E0382，process 里 save 之后又 notify
领域 WHY：成交记录是不可变事实，要单一来源，不该变成两份可分叉的拷贝
设计 WHAT：Arc<TradeRecord> 共享；不要 record.clone()
```

```rust
// ✗ 没回答「为什么两处都要」
save_to_db(record.clone());
notify(record);

// ✓ 领域结论：审计事实 = 共享不可变
fn process(record: Arc<TradeRecord>) {
    save_to_db(Arc::clone(&record));
    notify(Arc::clone(&record));
}
```

## 三振协议

同一处错误修补 3 次仍不过：停止局部修补 → 升级设计层（[shape.md](shape.md) 四问）→ 记录三振位置、重建模结论、之前方向为何错。三振过的搏斗几乎总值得 `/rust-skills:rust capture`。

拼写/缺 import/纯语法：不走三层、不三振；已获写入授权时一次改掉，否则只指出位置与补丁。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → **追溯链 + 方案对照表** → 验证 → 置信度 → 下一步 → 写授权收尾。
