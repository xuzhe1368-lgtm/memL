# memL 权限分层（RBAC）

## tenant role
- `viewer`：只读（可搜索、可查看、可统计）
- `editor`：读写（可新增/更新/删除）
- `admin`：读写（同 editor）

> 说明：系统管理接口 `/admin/*` 仍由 `MEML_ADMIN_TOKEN` 控制。

## 配置示例（tenants.yaml）

```yaml
tenants:
  sk-local-personal:
    name: personal
    collection: personal
    role: editor
    enabled: true

  sk-local-readonly:
    name: readonly
    collection: personal
    role: viewer
    enabled: true
```

## 行为约束
- `viewer` 调用 `POST/PATCH/DELETE /memory` 将返回 `403`
- `editor/admin` 可正常读写
