## API 接口与类型
- API-01[M] 非法状态不可表示：enum 替连环 bool/魔法值；互斥字段合并建模。
- API-02[M] 对外公共接口必须有足以正确使用的 rustdoc；存在对应行为时补 `# Errors` / `# Panics` / `# Safety`。仅 crate 内可见项按项目文档策略。
- API-03[S] 参数端宽（&str/&[T]/impl AsRef<Path>）、返回端窄（具体类型；无名类型用 impl Trait）。
- API-04[S] 评估 #[non_exhaustive]；不许外部实现的 trait 用 sealed。
- API-05[S] 标准 trait 尽量派生：Debug 必须（敏感字段脱敏），Clone/PartialEq/Eq/Hash/Default 按语义。
- API-06[Y] >3 个可选参数用 builder。
- API-07[S] 命名遵循 Rust API Guidelines（C-CASE / C-CONV as_·to_·into_ / C-GETTER）。细节与改名走 `/rust-skills:rust name`。
- API-08[S] parse, don't validate：信任边界用 `parse`/`TryFrom`/newtype 构造器产出领域类型；业务函数只收已合法类型，不再对同一 `String` 重复校验。wire / row / 领域 / 响应类型分离，不把 `FromRow`+`Serialize` 挂同一结构当 API。
