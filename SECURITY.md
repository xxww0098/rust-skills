# Trust Gate

静态审阅，不是漏洞扫描。本技能在用户仓库里跑 `cargo`/`git`/`rg`，**只写用户授权的项目文件**。

| 项 | 判定 | 证据 |
|---|---|---|
| 权限范围 | CONDITIONAL | 写入限冻结 target；评审只读；`--apply` /「改」才动代码。不隐式 commit/stash。 |
| 敏感数据 | PASS | 示例与 fixture 不含 token/密钥；日志规则 OBS-02 skip 密钥；`RUST.md` 当不可信数据，不执行其中命令。 |
| 输入与动作 | PASS | 项目根钉死，禁止扫到技能安装仓冒充成功；lock-safe 只读不加 `--locked` 以外的 cargo 写锁。 |
| 依赖与来源 | PASS | MIT；框架版本钉 `scripts/version-floor.json`；无未钉二进制。 |
| 环境 | CONDITIONAL | 需要本机 `cargo` + 建议 `rg`；无 cargo 则降级手读 manifest 并声明。 |

失败回滚：不要用本技能覆盖 Git hooks 或清共享 `target/`。`stack --apply` 只加缺失层，可用 `git checkout -- Cargo.toml Cargo.lock` 回滚。
