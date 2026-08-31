## OWN 所有权
- OWN-01[M] 不为过编译器而 clone：引入 clone 消除 E0382/E0507 前必须先答 D-6（谁该拥有）。共享不可变用 `&`/`Arc`；确需副本时在调用点注释「为何两处都要所有权」。
- OWN-02[S] 参数借用不拥有：禁 `&String`/`&Vec<T>`/`&PathBuf`，改 `&str`/`&[T]`/`&Path`（API-03）。调用方已有所有权且函数必须留下值时再收 `String`/`Vec`。
- OWN-03[S] 需要「拿走再放回」用 `mem::take`/`mem::replace`，不先 clone 再覆盖原位。
- OWN-04[S] 只有智能指针才 `impl Deref`/`DerefMut`（API Guidelines C-DEREF）。newtype 用 `as_str`/`AsRef`/`AsMut`（C-CONV-TRAITS）。项目已对透明包装统一 Deref 并写明约定时，按约定推翻并记录，不升 M。
- OWN-05[S] `Cell`/`RefCell`/`Mutex` 是所有权拆分失败后的工具，不是默认共享模型；引入时写明互斥与重入假设。
