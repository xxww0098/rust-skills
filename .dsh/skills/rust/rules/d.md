## D 决策树
- D-1 落点：先 `rg` 共享函数/类型/常量的全部调用方、平行入口、`#[cfg]` 分支与生成输入，再把变化放到拥有该不变量的现有模块；同类路径要么一起修，要么逐项说明不受影响。拆分走 WS-11 三级（函数 → `mod` → crate）；只有 WS-12 才新建 crate。不按行数阈值拆，也不另开拆分命令。
- D-2 错误：调用方要编程处理→稳定具名错误（手写或 thiserror，ERR-01/08）；应用编排→项目已有 anyhow/eyre，没有则不必为小 bin 新加；局部可证不可失败→expect("invariant:…")；不变量破坏→panic/debug_assert。
- D-3 共享状态：能消息传递/单一所有权→改；临界区短不跨 await→std Mutex；须跨 await→先重构再 tokio Mutex；度量证明锁瓶颈→细分/无锁+Ordering 论证+loom。
- D-4 新依赖：比较 std/现有方案的维护成本与成熟依赖的正确性、维护、传递代价和 license；理解 feature 后最小化启用，有实质存疑再请示。
- D-5 unsafe：有安全写法→用之；性能动机→安全版 bench 证明不足才引入：最小作用域+SAFETY+封装+Miri/loom。
- D-6 编译错误分诊：E0382/E0507→谁该拥有数据（共享不可变→&/Arc，确需副本才 clone 并说明，OWN-01）；E0597/E0515/E0716→作用域边界对吗（禁反射加 'static）；E0499/E0502→数据该拆吗（重构无果才内部可变性，OWN-05）；E0277 Send/Sync→该跨线程吗（先答再 Rc→Arc）；2024 `!` fallback / `never_type_fallback_flowing_into_unsafe`→显式写 `()` 或具体 Ok 类型，禁让 `!` 流进 unsafe；3 次不过→三振升级设计层。
