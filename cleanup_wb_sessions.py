#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 会话缓存清理工具
==========================

作用：清理已删除会话遗留的「空工作目录」和「缓存」，避免程序刷新会话列表时
把空文件夹重新生成出来，并回收无用的索引文件。

背景/原理
----------
1. WorkBuddy 的会话记录存放在 `~/.workbuddy/workbuddy.db` 的 `sessions` 表里。
   删除会话只是软删除（`deleted_at` 置时间戳），不会立刻删掉它的
   cwd（工作目录）和配套缓存。
2. 配套缓存散落在 `.workbuddy` 下，按会话 ID（conversationId）命名：
   - artifact-index/<id>.json          纯索引缓存
   - changes-index/<id>.json           纯索引缓存
   - file-tree-manifests/<id>.json     纯索引缓存
   - changes-detail/<id>/              纯缓存目录（可整目录删）
   - projects/<由 cwd 生成的 slug>/     会话工作数据（含 transcript/tool-results）

用法
----
  python cleanup_wb_sessions.py                     # 预览（默认只读，不删除）
  python cleanup_wb_sessions.py --apply             # 执行清理
  python cleanup_wb_sessions.py --apply --deep      # 深度清理：连 projects/<slug> 一起删
  python cleanup_wb_sessions.py --apply --clean-orphans   # 额外清理无主缓存
  python cleanup_wb_sessions.py --db <路径>          # 指定数据库路径

安全策略
--------
- 默认只读预览，必须显式加 --apply 才会真正删除。
- 工作目录（cwd）永远只删「完全不含文件」的（纯空目录树）；含代码/数据的目录
  一律跳过，绝不误删你的文件。
- 纯索引缓存（artifact-index / changes-index / file-tree-manifests / changes-detail）
  可随时重建，直接删除无副作用。
- projects/<slug> 属于会话工作数据，默认不删（除非是空目录）；加 --deep 才整目录删。
- 全程不修改数据库，只读连接。
"""

import argparse
import os
import shutil
import sqlite3
import sys


def default_db_path():
    home = os.path.expanduser("~")
    return os.path.join(home, ".workbuddy", "workbuddy.db")


def cwd_to_slug(cwd):
    """把 cwd 路径转成 projects/ 目录下的 slug 名。

    例：C:/Users/LDX/Documents/code/foo  ->  c-Users-LDX-Documents-code-foo
    """
    if not cwd:
        return None
    p = cwd.replace("\\", "/").rstrip("/")
    if len(p) >= 2 and p[1] == ":":
        p = p[0].lower() + p[2:]
    return p.replace("/", "-")


def tree_contains_files(path):
    """目录树里是否含有文件（递归）。只判断有没有文件，不管子目录。"""
    for _root, _dirs, files in os.walk(path):
        if files:
            return True
    return False


def read_sessions(db_path):
    """只读打开数据库，返回 (live_ids, deleted)。

    live_ids : 未删除会话的 id 集合
    deleted  : [(id, cwd, title), ...] 已删除（deleted_at 非空）的会话
    """
    uri = "file:{}?mode=ro".format(db_path.replace("\\", "/"))
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        cur.execute("SELECT id, cwd, title, deleted_at FROM sessions")
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print("[错误] 读取 sessions 表失败：", e)
        sys.exit(1)
    finally:
        con.close()

    live_ids = set()
    deleted = []
    for r in rows:
        sid = r["id"]
        if r["deleted_at"] is None:
            live_ids.add(sid)
        else:
            deleted.append((sid, r["cwd"], r["title"]))
    return live_ids, deleted


def plan_actions(wb_root, live_ids, deleted, clean_orphans, deep):
    """构建清理计划。

    返回 (empty_dirs, cache_dirs, cache_files, skip_dirs)：
    - empty_dirs : 仅当为空目录树时才删的目录（cwd / projects slug）
    - cache_dirs : 纯缓存目录，直接整目录删（changes-detail/<id>；--deep 时含 projects）
    - cache_files: 纯索引缓存文件
    - skip_dirs  : 含文件、默认不动、提示用户（cwd / projects slug）
    """
    empty_dirs = []
    cache_dirs = []
    cache_files = []
    skip_dirs = []

    def _mark_dir(path):
        # 未做存在性判断，调用方保证
        if deep:
            cache_dirs.append(path)
        else:
            empty_dirs.append(path)

    # 1) 已删除会话
    for sid, cwd, title in deleted:
        # 工作目录：永远只删空目录树
        if cwd and os.path.isdir(cwd):
            empty_dirs.append(cwd)

        # projects/<slug>：默认空目录才删；--deep 整目录删
        slug = cwd_to_slug(cwd)
        if slug:
            proj = os.path.join(wb_root, "projects", slug)
            if os.path.isdir(proj):
                _mark_dir(proj)

        # 纯索引缓存文件
        for sub in ["artifact-index", "changes-index", "file-tree-manifests"]:
            f = os.path.join(wb_root, sub, sid + ".json")
            if os.path.isfile(f):
                cache_files.append(f)

        # 纯缓存目录（变化明细）
        d = os.path.join(wb_root, "changes-detail", sid)
        if os.path.isdir(d):
            cache_dirs.append(d)

    # 2) 可选：无主缓存清理（ID 不在任何存活会话里）
    if clean_orphans:
        for sub in ["artifact-index", "changes-index", "file-tree-manifests"]:
            d = os.path.join(wb_root, sub)
            if not os.path.isdir(d):
                continue
            for name in os.listdir(d):
                if name.endswith(".json") and name[:-5] not in live_ids:
                    cache_files.append(os.path.join(d, name))
        cd = os.path.join(wb_root, "changes-detail")
        if os.path.isdir(cd):
            for name in os.listdir(cd):
                if name not in live_ids:
                    cache_dirs.append(os.path.join(cd, name))

    # 去重
    empty_dirs = list(dict.fromkeys(empty_dirs))
    cache_dirs = list(dict.fromkeys(cache_dirs))
    cache_files = list(dict.fromkeys(cache_files))

    # 空目录里，实际含文件的归入 skip_dirs
    final_empty = []
    for d in empty_dirs:
        if not os.path.isdir(d):
            continue
        if tree_contains_files(d):
            skip_dirs.append(d)
        else:
            final_empty.append(d)

    return final_empty, cache_dirs, cache_files, skip_dirs


def _dedup_print(label, items, prefix):
    print("%s（共 %d 个）：" % (label, len(items)))
    for it in items:
        print("  %s %s" % (prefix, it))
    print()


def main():
    ap = argparse.ArgumentParser(description="清理 WorkBuddy 已删除会话的缓存与空目录")
    ap.add_argument("--db", default=default_db_path(), help="workbuddy.db 路径")
    ap.add_argument("--apply", action="store_true", help="真正执行删除（默认只预览）")
    ap.add_argument("--deep", action="store_true",
                    help="深度清理：连 projects/<slug> 会话工作目录一起删")
    ap.add_argument("--clean-orphans", action="store_true",
                    help="额外清理无主缓存（ID 不在任何存活会话里）")
    args = ap.parse_args()

    if not os.path.isfile(args.db):
        print("[错误] 找不到数据库：", args.db)
        sys.exit(1)

    wb_root = os.path.dirname(args.db)
    live_ids, deleted = read_sessions(args.db)

    print("数据库：", args.db)
    print("存活会话：", len(live_ids), "  已删除会话：", len(deleted))
    print()

    empty_dirs, cache_dirs, cache_files, skip_dirs = plan_actions(
        wb_root, live_ids, deleted, args.clean_orphans, args.deep)

    if not empty_dirs and not cache_dirs and not cache_files:
        print("没有需要清理的内容，已是最干净状态。")
        return

    _dedup_print("将删除的空目录", empty_dirs, "[DIR ]")
    _dedup_print("将删除的缓存目录", cache_dirs, "[CACHE]")
    _dedup_print("将删除的缓存文件", cache_files, "[FILE]")
    if skip_dirs:
        _dedup_print("跳过（含文件，默认不动；加 --deep 可删 projects 目录）", skip_dirs, "[SKIP]")

    if not args.apply:
        print("预览模式：未做任何修改。确认无误后加 --apply 执行。")
        return

    n_dir = n_file = 0
    for d in empty_dirs:
        try:
            shutil.rmtree(d)
            n_dir += 1
            print("已删除目录：", d)
        except OSError as e:
            print("删除失败：", d, "->", e)
    for d in cache_dirs:
        try:
            shutil.rmtree(d)
            n_dir += 1
            print("已删除缓存目录：", d)
        except OSError as e:
            print("删除失败：", d, "->", e)
    for f in cache_files:
        try:
            os.remove(f)
            n_file += 1
            print("已删除文件：", f)
        except OSError as e:
            print("删除失败：", f, "->", e)

    print()
    print("完成：删除 %d 个目录、%d 个文件。" % (n_dir, n_file))


if __name__ == "__main__":
    main()
