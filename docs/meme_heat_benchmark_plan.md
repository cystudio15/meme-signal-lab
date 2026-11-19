# Meme 热度基准库方案

## 为什么不能只选有名的成功币

只研究最后成功的 Meme 会产生幸存者偏差。基准库必须同时包含：

- 持续扩散或形成较大市场的案例
- 短时爆发后快速衰退的案例
- 高社媒、低交易确认的案例
- 高交易、低自然讨论或推广主导的案例

## 匹配规则

每次比较至少匹配：

- chain
- token_age_bucket：`0-6h / 6-24h / 1-7d / 7-30d / 30d+`
- liquidity_bucket_usd
- market_cap_bucket_usd
- observation_window：统一使用事件前 24h 到事件后 72h，另保留 5m/15m/1h 窗口

DOGE、PEPE 等成熟资产不能直接用绝对成交量与刚创建的 AX1 比较；它们只适合做成熟阶段参考。

## 样本构成

第一版目标为 40 个案例：

- 10 个持续扩散案例
- 10 个短时爆发后衰退案例
- 10 个推广/平台事件主导案例
- 10 个自然社区扩散案例

2026 参考来源包括 CoinGecko季度行业报告、Meme分类榜和 GeckoTerminal Meme 交易榜。案例进入基准库前仍需核验合约、链、事件时间和池地址。

## 统一字段

登记表见 `data/manual/meme_heat_benchmark_registry.csv`。市场时间序列字段：

- `timestamp_utc`
- `txns_5m/15m/1h`
- `buys`、`sells`、`unique_traders`
- `volume_usd`、`liquidity_usd`、`volume_liquidity_ratio`
- `price_change`、`max_favorable_excursion`、`max_drawdown`

社媒时间序列字段：

- `post_count`、`unique_authors`
- `original/quote/retweet/reply_count`
- `weighted_interactions`
- `top_10_author_share`
- `duplicate_text_share`、`low_information_reply_share`

## 校准方法

1. 对偏态指标先做 `log1p`，避免一个超级大值压住所有样本。
2. 在匹配组内计算百分位，而不是全市场使用固定阈值。
3. 分别计算社媒热度和交易热度，不把价格涨幅直接混入热度。
4. 使用时间先后判断 `early / brewing / crowded / distribution-risk`。
5. 回测热度分与后续交易、回撤和流动性结果的关系，再调整权重。

## 当前状态

当前已经完成两种不同层级中的第一种：

1. **同阶段市场快照基准（已完成）**：从389个 Base 新池和趋势池中，按币龄与流动性的对数距离选择40个最接近AX1的池，计算成交额、交易笔数、独立交易者和成交额/流动性百分位。它可以回答“AX1此刻相对同阶段池有多活跃”。
2. **历史结果与社媒真实性基准（未完成）**：登记表中的成功、衰退、推广和自然扩散条目仍是研究队列。至少完成每类10个历史案例后，才能回答“这种热度以后通常怎样”以及校准跨币社媒热度等级。

因此AX1可以显示**市场活跃度快照百分位**，但仍不显示综合投资分或跨币社媒热度分。
