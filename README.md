# WorkBuddy Session Cleaner

清理 WorkBuddy（WorkDaddy）已删除会话的缓存与空目录，避免「删了又自动生成空文件夹」的问题。

## 它解决什么问题

WorkBuddy 删除一个会话时，只是对数据库里的记录做「软删除」（`deleted_at` 置时间戳），并不会立刻删掉它的：

- 工作目录（cwd）—— 可能残留成空文件夹
- 配套缓存索引（`artifact-index` / `changes-index` / `file-tree-manifests` / `changes-detail`）

程序刷新会话列表时，会按「未删除」的会话重建工作目录；而跨账号的重复会话记录，会导致你已经删除的文件夹被再次「复活」成空目录。

本工具只读数据库，识别出已删除的会话，并安全地清理它们的残留。

## 快速开始

直接把仓库下载到本地，然后双击对应的 `.bat` 即可（Windows）：

| 脚本 | 作用 | 说明 |
| --- | --- | --- |
| `1_cleanup_preview.bat` | 预览 | 只读查看，不删除任何东西 |
| `2_cleanup_apply.bat` | 执行清理 | 清空目录 + 纯缓存（安全） |
| `3_cleanup_deep.bat` | 深度清理 | 额外删除 `projects/<slug>` 会话数据，需输入 Y 确认 |
| `4_cleanup_orphans.bat` | 清无主缓存 | 额外清理 ID 已不在任何存活会话里的缓存 |

也可以直接用 Python 运行：

```bash
# 预览（默认只读，不删除）
python cleanup_wb_sessions.py

# 执行清理
python cleanup_wb_sessions.py --apply

# 深度清理（连 projects 会话数据一起删）
python cleanup_wb_sessions.py --apply --deep

# 额外清理无主缓存
python cleanup_wb_sessions.py --apply --clean-orphans

# 指定数据库路径
python cleanup_wb_sessions.py --db <路径>
```

## 清理内容

针对每个「已删除」的会话，清理四类残留：

| 类型 | 内容 | 处理方式 |
| --- | --- | --- |
| 空工作目录 | 会话的 cwd | **只删不含文件的**，有代码就跳过 |
| 缓存目录 | `changes-detail/<会话ID>/` | 纯缓存，整目录删 |
| 缓存索引 | `artifact-index` / `changes-index` / `file-tree-manifests` 下的 json | 纯索引，直接删 |
| 会话工作数据 | `projects/<slug>/` | 默认只删空目录，`--deep` 才整删 |

## 安全策略

- 默认只读预览，必须显式加 `--apply` 才会真正删除。
- 工作目录永远只删除「完全不含文件」的目录树；含代码/数据的目录一律跳过，绝不误删你的文件。
- 纯索引缓存可随时重建，删除无副作用。
- 全程不修改数据库，只读连接。

## 依赖

- Python 3（标准库即可，无第三方依赖）
- Windows 下的 `.bat` 脚本会优先调用内置的托管 Python，找不到则回退到系统 `python`

## License

[MIT](LICENSE)
