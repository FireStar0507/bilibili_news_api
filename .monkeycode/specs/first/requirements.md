# Requirements Document

## Introduction

本系统是面向个人学习测试的 B 站单会话私信本地归档工具。系统通过 B 站官方私信接口 `fetch_session_msgs` 拉取同一会话的私信，将消息元数据持久化到仓库内 SQLite，将图片按年/月/旬目录写入仓库。v1 只负责记录与回写，不实现查阅界面。

系统采用双轨同步模型：增量同步追平本地最大 seqno 之后的全部新消息；回溯补历史低频分批补齐更早消息。两条流程互相独立。GitHub Actions 每日运行增量同步，将数据库、图片、断点提交回仓库。

本系统仅用于归档当前登录账号与指定会话对象之间的私信，规模目标为 10 万条以上消息。本仓库无旧存档，图片目录采用新分层规则。

## Glossary

- **System / 归档系统**: 本需求描述的 B 站私信单会话本地归档工具。
- **Session / 会话**: 当前登录账号与一个 `talker_id` 之间的私信通道。`session_type=1` 表示用户会话。
- **talker_id**: 聊天对象 ID。用户会话中为对方 mid。
- **seqno / msg_seqno**: B 站接口给出的消息唯一递增序列号。接口层面每条消息 `seqno` 唯一，系统以该字段作为主键与去重依据。
- **begin_seqno**: 请求参数。传入某条消息的 `seqno` 时，接口返回该序列号之前（不含该序列号）的更早消息。
- **min_seqno**: 当前响应批次中最小的 `seqno`。回溯时将其作为下一轮 `begin_seqno`。
- **max_seqno**: 当前响应批次中最大的 `seqno`，对应该批最新消息。
- **has_more**: 接口字段。`1` 表示仍有更早消息；`0` 表示已到达会话最早消息。
- **SESSDATA**: B 站身份 Cookie。过期后接口返回 `-101`。
- **msg_type**: 消息类型。`1` 为文本，`2` 为图片。其他类型 content 结构不固定。
- **msg_status**: 消息状态。`0` 正常，`1` 撤回（接口仍返回撤回内容），`2` 系统撤回，`50` 图片已失效。
- **Archive Set / 完整存档备份集合**: 仓库内 `bilibili_msg_archive.db`、按年/月/旬存放的图片目录、`resume_point.json` 三者组成的完整备份。
- **Image Bucket / 图片存储桶**: 以消息 `timestamp` 的 UTC 日期计算。路径 `{YYYY}/{MM}/{DD-DD}`，每月三个旬：`01-10`、`11-20`、`21-{月末日}`。月末不足十日并入下旬。
- **Incremental Sync / 增量同步**: 读取本地当前会话最大 `seqno`，循环拉取最新消息直到本批已无更大 seqno，仅入库更大的新增消息。不读写 `resume_point.json`。
- **Backfill / 回溯补历史**: 低频分批流程。读取 `resume_point.json`，按批次向前拉取更早消息，每批写入断点，支持 `max_round` 限制。
- **Rate Limit Interval / 请求间隔**: 相邻两次接口请求之间的最短等待时间，用于规避 B 站 412 风控。

## Requirements

### Requirement 1: 个人单会话归档范围

**User Story:** AS 个人使用者, I want 将当前登录账号与指定会话对象之间的私信持久保存到本地, so that B 站服务不可访问时我仍能查阅该会话存档。

#### Acceptance Criteria

1. WHEN 使用者提供有效的 `SESSDATA`、`talker_id` 与 `session_type`, THE 归档系统 SHALL 仅拉取该会话的私信。
2. THE 归档系统 SHALL 将消息元数据写入 SQLite 数据库文件 `bilibili_msg_archive.db`。
3. THE 归档系统 SHALL 将图片文件写入本地目录 `msg_images/`。
4. THE 归档系统 SHALL 将用途限定为当前登录账号的个人学习测试。
5. v1 THE 归档系统 SHALL 只实现记录、下载与回写，不实现查阅界面。

### Requirement 2: 固化存档数据规范

**User Story:** AS 个人使用者, I want 新写入的数据与既有存档使用同一套表结构、路径规则和断点格式, so that 已有数据库、图片文件和断点文件可以继续使用。

#### Acceptance Criteria

1. THE 归档系统 SHALL 使用表名 `private_messages`，主键为 `seqno INTEGER PRIMARY KEY`。
2. THE 归档系统 SHALL 在 `private_messages` 中包含且仅依赖以下字段：`seqno, talker_id, sender_uid, timestamp, msg_type, msg_status, content_text, raw_content, image_local_path, created_at`。
3. WHEN 归档系统计算图片目录, THE 归档系统 SHALL 使用相对仓库根的路径 `{YYYY}/{MM}/{DD-DD}/{seqno}.后缀`。旬划分为 `01-10`、`11-20`、`21-{该月最后一天}`。
4. WHEN 归档系统保存图片文件, THE 归档系统 SHALL 使用文件名 `{seqno}.后缀`，并在 `image_local_path` 中存储上述相对路径。
5. THE 归档系统 SHALL 将断点文件命名为 `resume_point.json`，其 key 为字符串类型 `talker_id`，value 包含 `last_begin_seqno` 与 `has_finished`。
6. WHEN 使用者备份完整存档, THE 归档系统 SHALL 将 `bilibili_msg_archive.db`、年/月/旬图片目录、`resume_point.json` 视为缺一不可的备份集合。

### Requirement 3: 消息去重与时序查询

**User Story:** AS 个人使用者, I want 每条消息只保存一次，并按聊天先后顺序展示, so that 10 万级存档不会重复、也不会因时间戳碰撞而乱序。

#### Acceptance Criteria

1. WHEN 一条消息的 `seqno` 已存在于 `private_messages`, THE 归档系统 SHALL 跳过该条消息的入库。
2. WHEN 使用者按聊天先后顺序查询消息, THE 归档系统 SHALL 使用 `ORDER BY seqno ASC`。
3. THE 归档系统 SHALL 以 `seqno` 作为唯一标识与排序依据。
4. THE 归档系统 SHALL 在 `seqno` 为 10 万级规模时保持去重判断与按 `seqno` 查询可用。

### Requirement 4: 增量同步新消息

**User Story:** AS 个人使用者, I want 高频轻量地收录持续产生的新消息, so that 最新对话可以稳定进入本地存档。

#### Acceptance Criteria

1. WHEN 增量同步启动, THE 归档系统 SHALL 读取本地当前会话已入库消息的最大 `seqno`。
2. WHEN 本地当前会话尚无消息, THE 归档系统 SHALL 将本地最大 `seqno` 视为 0 并拉取最新一批消息。
3. WHEN 增量同步收到一批消息, THE 归档系统 SHALL 仅入库 `seqno` 大于本地最大 `seqno` 的消息。
4. WHILE 本批仍存在 `seqno` 大于本地最大 `seqno` 的消息, THE 归档系统 SHALL 继续拉取下一批并更新本地最大 `seqno`，直到本批全部不大于本地最大 `seqno` 或本批为空。
5. THE 增量同步流程 SHALL 独立于回溯补历史流程运行。
6. THE 增量同步流程 SHALL 在运行期间保持不读写 `resume_point.json`。

### Requirement 5: 回溯补历史与断点续跑

**User Story:** AS 个人使用者, I want 分批向前补齐历史消息并在中断后从断点继续, so that 10 万级历史可以在风控可接受的节奏下逐步补全。

#### Acceptance Criteria

1. WHEN 回溯补历史启动, THE 归档系统 SHALL 读取 `resume_point.json` 中对应 `talker_id` 的断点。
2. WHEN 对应 `talker_id` 尚无断点记录, THE 归档系统 SHALL 从不携带 `begin_seqno` 的最新一批开始，取该批 `min_seqno` 作为后续回溯起点。
3. WHEN 一批回溯请求完成且消息已处理, THE 归档系统 SHALL 将该批 `min_seqno` 写入 `last_begin_seqno`。
4. WHEN 接口返回 `has_more=0`, THE 归档系统 SHALL 将该会话 `has_finished` 标记为 `true` 并结束回溯。
5. WHEN 本轮已完成的请求批次数达到 `max_round`, THE 归档系统 SHALL 停止本轮回溯并保留当前断点。
6. WHILE 对应会话 `has_finished` 为 `true`, THE 归档系统 SHALL 跳过对该会话的回溯请求。
7. THE 回溯补历史流程 SHALL 独立于增量同步流程运行。

### Requirement 6: 接口倒序分页与请求节流

**User Story:** AS 个人使用者, I want 系统按接口原生倒序能力分页，并在请求之间保留间隔, so that 历史可以向前翻页，同时账号避免触发 412 风控。

#### Acceptance Criteria

1. WHEN 归档系统请求最新一批消息, THE 归档系统 SHALL 调用 `https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs` 且不传 `begin_seqno`。
2. WHEN 归档系统需要更早的消息, THE 归档系统 SHALL 传入 `begin_seqno` 等于上一批 `min_seqno`。
3. WHEN 归档系统调用私信接口, THE 归档系统 SHALL 使用 Cookie 中的 `SESSDATA` 进行身份认证。
4. WHEN 相邻两次接口请求之间, THE 归档系统 SHALL 等待可配置的请求间隔，默认间隔不少于 1.5 秒。
5. THE 归档系统 SHALL 将单次请求的 `size` 设为可配置参数，默认值为 20，上限为 200。

### Requirement 7: 文本与图片解析入库

**User Story:** AS 个人使用者, I want 文本和图片被专门解析，其他类型完整保留原始内容, so that 常见消息可直接阅读，未知类型也不会丢失。

#### Acceptance Criteria

1. WHEN 消息 `msg_type=1`, THE 归档系统 SHALL 从 content JSON 的 `content` 字段提取文本写入 `content_text`，并将原始 content 写入 `raw_content`。
2. WHEN 消息 `msg_type=2`, THE 归档系统 SHALL 从 content JSON 的 `url` 字段下载图片到对应存储桶，将相对路径写入 `image_local_path`，并将原始 content 写入 `raw_content`。
3. WHEN 消息 `msg_type` 为 1 与 2 以外的值, THE 归档系统 SHALL 将原始 content 写入 `raw_content`，并将 `content_text` 与 `image_local_path` 留空。
4. WHEN 消息 `msg_status=1`, THE 归档系统 SHALL 仍然入库该消息及其接口返回的内容。
5. WHEN 图片下载失败, THE 归档系统 SHALL 仍然入库该消息的文本与 `raw_content`，并将 `image_local_path` 留空。

### Requirement 8: 身份失效与接口错误处理

**User Story:** AS 个人使用者, I want 凭证过期或接口失败时得到明确停止原因, so that 我可以更新 SESSDATA 或稍后重试，而不会把错误当成正常结束。

#### Acceptance Criteria

1. WHEN 接口返回 `code=-101`, THE 归档系统 SHALL 停止当前流程并提示 `SESSDATA` 已失效，需要使用者更新凭证。
2. WHEN 接口返回 HTTP 412 或明确的风控拦截, THE 归档系统 SHALL 停止当前流程并保留已写入的数据和断点。
3. WHEN 接口返回 `code=0` 且 `messages` 为空或 `null`, THE 归档系统 SHALL 将该次请求视为无新消息并正常结束本轮拉取。
4. IF 单次请求网络失败, THE 归档系统 SHALL 按可配置次数重试，重试耗尽后停止当前流程并保留已写入的数据和断点。

### Requirement 9: GitHub Actions 每日回写

**User Story:** AS 个人使用者, I want 每天由 GitHub Actions 自动跑增量同步并把结果提交回仓库, so that 存档随仓库一起保存，数据库仍是仓库内的本地 SQLite 文件。

#### Acceptance Criteria

1. THE 归档系统 SHALL 提供 GitHub Actions 工作流，按 cron 每天至少运行一次增量同步。
2. WHEN Actions 运行, THE 归档系统 SHALL 从 GitHub Secrets 读取 `SESSDATA`，并从仓库检出已有的 `bilibili_msg_archive.db`、图片目录与 `resume_point.json`。
3. WHEN 增量同步结束且工作区有变更, THE 归档系统 SHALL 将数据库、新增图片与相关文件提交并推回同一仓库。
4. WHEN `SESSDATA` 缺失或接口返回 `-101`, THE Actions 作业 SHALL 以失败结束且不强制清空已有存档。
5. THE Actions 每日作业 SHALL 默认只跑增量同步；回溯补历史由手动 `workflow_dispatch` 触发并遵守 `max_round`。
