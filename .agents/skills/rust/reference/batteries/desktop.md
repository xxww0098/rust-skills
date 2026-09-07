# 桌面 kit

目的：给产物 `desktop` 一份最小 crate 工具箱。先读 [batteries.md](../batteries.md)；本文件只填 kit。版本只取 floor。

```
id: desktop/min
product_types: desktop
required_facets: artifact=desktop · 用户词含桌面/Tauri
optional_facets: 插件/托盘/菜单 · 移动端
exclude_facets: 无 UI 的 HTTP 服务 · 纯 GPU 工具已有 egui（保留，不迁）
required_layers: 桌面壳
recommended_crates: tauri
optional_crates: （无。插件与 capabilities 走 /tauri，不在 kit 里预装）
crate_roles:
  tauri — 桌面壳（ST-07）。前端沿用团队已有 Vite 栈，本命令不加 npm 全家桶
floor_keys: tauri
conflict_rules: 新桌面不荐 egui/iced/gtk 当默认；已有 egui 且用户要纯 GPU 工具 → 保留；tauri 1 当新项目标先迁
rationale: 一个壳就够开工。鉴权/HTTP 服务/ORM 不是桌面最小 kit（BAT-06）
apply_actions: 现状=无才按 floor 加 tauri；不改 capabilities、不写前端
```

未点名桌面时本文件不打开。HTTP API 在隔壁 crate 就走 http-service，不要塞进同一 kit。
