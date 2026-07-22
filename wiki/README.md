# MERJIC 概念 Wiki

这是概念库的网页阅读层。内容仍以根目录的 `概念页/*.md` 为唯一来源，网页文件由构建脚本自动生成。

## 本地预览

在 Finder 中双击项目根目录的 `打开概念Wiki.command` 即可启动并打开网站。

也可以在终端中运行：

```bash
rtk python3 wiki/dev_server.py
```

然后访问 `http://127.0.0.1:4173`。

持续预览服务会监听 `概念页/*.md`：新增、修改或删除概念后，会自动同步 SQLite 和 JSON 索引、重建网页，并通知浏览器刷新。`wiki/src/` 的界面代码发生变化时也会自动重建。

## 公开站内容同步

公开站优先读取 GitHub `main` 分支的 `wiki/dist/concepts.json`。本机的概念同步服务每 5 分钟检查一次概念页：发现内容变化后会重建数据并同步到 GitHub。GitHub 更新后，公开站的读者刷新页面即可取得新内容；缓存通常不超过数分钟。


## 更新内容

正式生成一次静态网页时，也可以手动运行：

```bash
rtk python3 scripts/sync_db.py --incremental
rtk python3 scripts/build_index.py --incremental
rtk python3 wiki/build.py
```

`wiki/src/` 存放网页源文件，`wiki/dist/` 是可直接部署的静态站点。
