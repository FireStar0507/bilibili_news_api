# B 站私信单会话本地归档

个人学习测试用。通过 `fetch_session_msgs` 把同一会话私信写入仓库内 SQLite，图片按 `年/月/旬` 落盘。v1 只记录，不提供查阅界面。

## 命令

```bash
python -m src.cli sync
python -m src.cli backfill --max-round 10
python -m src.cli status
```

复制 `config.example.json` 为 `config.json`，或设置环境变量 `BILI_SESSDATA`、`BILI_TALKER_ID`。

## GitHub Actions

仓库 Secrets 必填：`BILI_SESSDATA`、`BILI_TALKER_ID`。每天 UTC 16:00 跑增量同步，把 db 与图片 commit 回仓库。手动 `workflow_dispatch` 可选 `backfill`。

## 存档

- `bilibili_msg_archive.db`
- `{YYYY}/{MM}/{01-10|11-20|21-月末}/{seqno}.ext`
- `resume_point.json`（仅回溯使用）
