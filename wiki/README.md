# MERJIC 概念 Wiki

这是概念库的网页阅读层。内容仍以根目录的 `概念页/*.md` 为唯一来源，网页文件由构建脚本自动生成。

## 本地预览

```bash
rtk python3 wiki/build.py
rtk python3 -m http.server 4173 --directory wiki/dist
```

然后访问 `http://127.0.0.1:4173`。

## 更新内容

概念页新增或修改后，先按项目约定同步数据库，再重新构建网页：

```bash
rtk python3 scripts/sync_db.py --incremental
rtk python3 scripts/build_index.py --incremental
rtk python3 wiki/build.py
```

`wiki/src/` 存放网页源文件，`wiki/dist/` 是可直接部署的静态站点。
