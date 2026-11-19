# Kafka/Flink 实时扩展设计

## 当前版与实时版的关系

当前作品是批处理：Go 采集公开 JSON，Python 读取 CSV/JSON，验证后生成指标与页面。
它适合小样本、可审计研究。Kafka/Flink 不是为了在简历上堆技术，而是在事件持续高速到来时解决
吞吐、顺序、迟到数据和实时窗口问题。

## 目标架构

```text
X API / 新闻 / DEX / BNB RPC
        ↓ Go collectors
Kafka topics
├── social-events-v1
├── market-events-v1
├── wallet-events-v1
└── contract-risk-events-v1
        ↓
Flink
├── Schema 校验与死信队列
├── URL/Tx Hash 幂等去重
├── UTC event-time + watermark
├── 5m / 15m / 1h 滚动窗口
├── 钱包标签时态 Join
└── 信号特征与证据准备度
        ↓
PostgreSQL/ClickHouse + Object Storage Raw
        ↓
Signal API → 产品页面/推送/实验分析
```

## Kafka 为什么需要

- 解耦采集与计算：X 变慢时不会直接拖垮市场处理
- 保留事件顺序和可重放日志
- 多个消费者可分别做实时评分、存档和监控
- 通过 key 控制同一 CA 的事件进入同一分区

建议 key：`chain + contract_address`。每条消息必须带 `event_id`、`event_time_utc`、
`collected_at_utc`、`schema_version` 和 `source_id`。

## Flink 为什么需要

- Event Time：按事件真正发生时间计算，而不是按到达服务器时间
- Watermark：允许 X、RPC 等来源迟到，同时控制等待上限
- Window：计算 5/15/60 分钟讨论量、钱包买家数和成交变化
- Stateful Dedup：防止重试导致一条帖子或交易重复计数
- Temporal Join：用事件发生当时的钱包标签版本做关联，避免未来信息泄漏

## 一个 15 分钟信号窗口

```text
输入：同一 CA 的 social + wallet + market 事件
窗口：事件时间滚动 15 分钟，每 1 分钟更新
输出：
- unique_accounts_15m
- duplicate_ratio
- affiliate_share
- wallet_buyers_15m
- dev_net_flow_usd_15m
- volume_change_15m
- evidence_readiness
```

钱包标签更新必须带 `valid_from/valid_to`。如果一个地址今天被识别为 DEV，不能把这个标签偷偷应用到
上个月的回测，除非能够证明标签当时已知。

## 错误与监控

| 情况 | 处理 |
|---|---|
| Schema 不兼容 | 写入 dead-letter topic，不进入评分 |
| API 429 | Go 指数退避，记录重试次数 |
| 重复消息 | 以 event_id/tx_hash 在状态中去重 |
| 事件迟到 | watermark 内更新窗口；超时写 late-events |
| 来源断流 | 监控每源最后事件时间和吞吐 |
| 评分字段缺失 | 降低准备度，不以 0 冒充业务事实 |

## 当前作品已经验证的迁移基础

- 稳定事件 Schema
- event time 与 collection time 分离
- 确定性 event_id 和去重
- Raw/Processed 分层
- 来源登记和证据等级
- 可解释评分及缺失数据规则

尚未完成：Kafka/Flink 实际部署、Schema Registry、Checkpoint、Exactly-once Sink 和生产监控。
该方案是可实施的扩展路径，不代表当前原型已经部署生产集群。
