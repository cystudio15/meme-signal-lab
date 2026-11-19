# GitHub 与 Streamlit 部署说明

## 1. 发布前检查

在项目目录运行：

```bash
./scripts/preflight_public.sh
./.venv/bin/python -m pytest -q
cd collector && go test ./...
```

确认 `.env`、Streamlit 密钥文件和原始 API 返回不会进入仓库：

```bash
git check-ignore -v .env .streamlit/secrets.toml data/raw/x
```

## 2. 创建 GitHub 仓库

建议仓库名：`meme-signal-lab`，选择 **Public**。

因为本地已有 README 和 `.gitignore`，创建时不要勾选自动生成 README、`.gitignore` 或 License。

首次提交前设置 Git 身份：

```bash
git config --global user.name "你的英文名或 GitHub 用户名"
git config --global user.email "<github-noreply-email>"
git add .
git status
git commit -m "Build Meme social signal research prototype"
git branch -M main
git remote add origin https://github.com/<github-user>/meme-signal-lab.git
git push -u origin main
```

`git status` 是最后一道人工检查：不应出现 `.env`、`secrets.toml`、`data/raw/` 或 `.venv/`。

## 3. 部署 Streamlit

在 Streamlit Community Cloud 新建应用：

- Repository：`<github-user>/meme-signal-lab`
- Branch：`main`
- Main file path：`app.py`
- Python version：`3.14`
- Secrets：留空

本项目的公开页面默认只读取已处理数据，不需要把 X Bearer Token 放到云端。CA 查询入口默认是只读演示；如需启用管理员入口，在 Streamlit Secrets 中配置：

```toml
ADMIN_ACCESS_CODE = "请使用独立强口令"
LIVE_CA_ANALYSIS_ENABLED = "false"
```

`LIVE_CA_ANALYSIS_ENABLED` 保持 `false` 时，即使管理员验证成功也不会触发实时采集。以后接入实时 X API 采集后，X Token 也只能放在云端 Secrets，不能提交到 GitHub。

## 4. 部署后验收

逐项检查：

1. AX1 与 NIULAI 都能切换。
2. 当前判断、生命周期、市场联动和风险区块正常显示。
3. 图表日期为北京时间，手机与电脑均可滚动。
4. 页面没有本机绝对路径、Token 或调试文字。
5. README 顶部补上在线网址。

以后更新代码：

```bash
git add .
git status
git commit -m "Describe the update"
git push
```

Streamlit Community Cloud 会从 GitHub 自动重新部署。
