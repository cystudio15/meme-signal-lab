# 数据字典与证据设计

## 1. 数据分层

### Raw 原始层

保存采集时得到的原始 JSON、HTML 摘要或人工记录，不覆盖、不修改。用于回答“这条结论从哪里来”。

### Processed 清洗层

统一字段名称、UTC 时间、链名称、CA 格式，完成去重和来源分类。

### Features 特征层

按代币和时间窗口计算讨论量、来源集中度、钱包确认、收益和回撤等指标。

### Presentation 展示层

仅包含网页需要的字段和解释，不直接修改底层数据。

## 2. 事件主表 `events`

| 字段 | 类型 | 示例 | 来源/规则 | 是否必须 |
|---|---|---|---|---|
| `event_id` | string | `evt_000001` | 程序生成的唯一编号 | 是 |
| `token_symbol` | string | `EXAMPLE` | 项目/市场数据 | 是 |
| `contract_address` | string | `0x...` | 原始来源；代币/链上事件必须有，平台或行业事件可空但会进入质量报告 | 条件必填 |
| `chain` | string | `bsc` | 标准枚举：`bsc/solana/...` | 是 |
| `event_type` | string | `social_post` | 社媒、钱包、市场、风险等 | 是 |
| `event_time_utc` | datetime | `2026-10-15T08:30:00Z` | 原始时间转 UTC | 是 |
| `collected_at_utc` | datetime | `2026-11-08T07:20:00Z` | 实际采集时间 | 是 |
| `source_platform` | string | `x` | X、Telegram、DEXScreener、explorer 等 | 是 |
| `source_url` | string | `https://...` | 原始证据链接 | 是 |
| `source_account` | string | `project_official` | 账号或实体名称 | 否 |
| `source_type` | string | `affiliate` | 分类规则见下文 | 是 |
| `raw_text` | string | `速度超快...` | 原始文本或合规摘要 | 否 |
| `language` | string | `zh` | ISO 简化代码 | 否 |
| `has_referral_link` | boolean | `true` | URL/文案规则 + 人工复核 | 是 |
| `is_duplicate` | boolean | `false` | 文本规范化后比较 | 是 |
| `duplicate_group_id` | string | `dup_003` | 相似文本分组 | 否 |
| `transaction_hash` | string | `0x...` | 区块浏览器/链上 API | 否 |
| `wallet_address` | string | `0x...` | 链上数据 | 否 |
| `wallet_label` | string | `smart_money` | 来源和版本必须记录 | 否 |
| `side` | string | `buy` | buy/sell/transfer | 否 |
| `usd_value` | number | `1240.50` | 交易时估值 | 否 |
| `price_usd` | number | `0.00042` | 市场数据，必须对齐时间 | 否 |
| `market_cap_usd` | number | `420000` | 市场数据 | 否 |
| `volume_5m_usd` | number | `30000` | 时间窗口数据 | 否 |
| `liquidity_usd` | number | `120000` | 池数据 | 否 |
| `dex_boost_amount` | number | `50` | DEX Screener 等公开记录 | 否 |
| `evidence_status` | string | `verified` | 见下方证据状态；不能用空值代替不确定性 | 是 |
| `notes` | string | `人工分类，待复核` | 假设和限制 | 否 |

## 3. X 帖子明细 `x_posts_preview`

该表由 Go 保存的 X API Raw JSON 经 Python 展平、类型转换和 `post_id` 去重生成。每一行是一条帖子，不等于一个独立市场事件。

| 字段 | 含义 |
|---|---|
| `post_id` | X 帖子唯一 ID，也是去重主键 |
| `created_at_utc` | 帖子发布时间，统一为 UTC |
| `author_id` | X 返回的作者 ID；当前未额外查询用户名资料 |
| `post_type` | `original/reply/quote/retweet` |
| `text` | API 返回的帖子原文 |
| `lang` | X 返回的语言代码 |
| `reply/retweet/like/quote_count` | API 返回的公开互动指标 |
| `impression_count` | API 返回的浏览量；0 不一定表示真实无人浏览 |
| `bookmark_count` | API 返回的收藏数；同样受访问权限影响 |
| `total_interactions` | 回复、转发、点赞、引用和收藏之和，不包含浏览量 |
| `referenced_post_ids` | 回复、引用或转发所关联的帖子 ID |
| `source_url` | 可点击核验的 X 原帖 URL |
| `search_query` | 本次采集使用的查询条件 |
| `collected_at_utc` | Go 采集器实际收到响应的 UTC 时间 |

### AX1 引用传播关系 `ax1_quote_edges`

| 字段 | 含义 |
|---|---|
| `root_post_id` | 被引用的 AX1 核心帖子 |
| `propagation_post_id` | 引用或继续放大的帖子 |
| `propagation_level` | `direct_quote` 为直接引用；`downstream_amplification` 为引用帖被继续转发 |
| `immediate_parent_ids` | 当前帖子直接引用、回复或转发的上一层帖子 ID |
| `immediate_relation_types` | 与上一层的 `quoted/retweeted/replied_to` 关系 |

关键词搜索不会自动继承被引用帖的正文，因此引用图是召回只写“4倍了”等低上下文传播帖的必要补充。

### AX1 社媒热度证据 `ax1_social_heat_evidence`

该文件只描述已观察到的注意力与传播证据，不输出投资评分。跨币热度等级尚未建立匹配基准，因此 `score_0_100` 明确为空。

| 字段 | 含义 |
|---|---|
| `interaction_mean/median/p90` | 互动量均值、中位数和第 90 百分位；共同展示以识别长尾 |
| `top_10_author_post_share` | 发帖最多的 10 个作者贡献占比 |
| `single_post_author_share` | 样本中只出现一次的作者比例 |
| `direct_quote_posts` | 直接引用核心帖的帖子数 |
| `downstream_amplification_posts` | 引用帖被继续转发或传播的帖子数 |
| `cross_query_duplicate_rate` | 五条查询轨之间的重复读取比例 |
| `quote_graph_unique_addition_rate` | 引用图为最终唯一帖子集合新增的比例 |
| `calibration.status` | `uncalibrated` 表示缺少同链、币龄、流动性和窗口匹配基准 |

`ax1_social_activity_hourly.csv` 按 UTC 小时保存帖子数、独立作者数和互动量。没有历史基线前，它只能显示活动变化，不能直接称为异常。

### AX1 市场活跃度基准 `ax1_market_heat_benchmark`

该文件从 GeckoTerminal 公共 API 的 Base 新池和趋势池建立采集时点的候选宇宙，再按币龄与流动性的对数距离选择 40 个最接近 AX1 的池。

| 字段 | 含义 |
|---|---|
| `volume_h24_usd` | 池在 API 快照中的 24 小时成交额 |
| `transactions_h24` | 24 小时买入与卖出笔数之和 |
| `unique_traders_h24` | 24 小时独立交易者数 |
| `volume_liquidity_ratio_h24` | 成交额除以流动性，用于比较资金周转强度 |
| `match_distance` | 币龄对数距离 + 0.5 × 流动性对数距离；越小越接近 AX1 |
| `metric_percentiles` | AX1 在 40 个同阶段池中的指标百分位 |

价格涨幅、FDV和市值不进入市场活跃度分数，避免把“已经上涨”循环解释成“热度更高”。该分数是当时快照排名，不是收益预测；候选宇宙也不是已全部人工确认的 Meme 历史结果库。

## 4. 策略画像与跨链候选

### 打狗策略画像 `degen_strategy_personas`

该表不是给用户贴永久标签，而是描述一次决策采用的策略模式。相同用户可以在不同交易中切换策略。

| 字段 | 含义 |
|---|---|
| `persona_name` | 极早期扫链、二段确认、热点叙事、聪明钱跟随等策略角色 |
| `entry_stage` | 该策略通常关注的新建、毕业、外盘或事件阶段 |
| `core_question` | 用户真正需要产品回答的问题 |
| `primary_signals` | 需要展示的市场、社媒、钱包或执行指标 |
| `hard_risk_gate` | 不满足时应停止继续判断的安全条件 |
| `execution_need` | 钱包、Bot、限价、防夹或组合风控需求 |
| `ax1_current_fit` | 现有证据下AX1与该策略的适配及缺口 |

`meme_2026_case_candidates.csv` 是跨链路径研究队列，不是已经验证的年度排行榜。`verification_status` 明确区分合约已核验、事件已核验、待补合约和页面暂不可访问。

## 5. 来源类型 `source_type`

| 值 | 定义 |
|---|---|
| `official_project` | 项目方官方账号或网站 |
| `official_platform` | 交易平台、发行平台等官方来源 |
| `kol` | 有稳定受众、发布观点或喊单的个人/机构账号 |
| `affiliate` | 包含返佣、邀请码、折扣或明确导流目的 |
| `community` | 普通社区讨论，未识别明确商业关系 |
| `paid_visibility` | 可验证的 Boost、广告或付费展示 |
| `bot_or_suspicious` | 高频重复、批量账号或疑似自动传播 |
| `news_media` | 媒体/资讯来源 |
| `onchain` | 链上交易、钱包或合约事件 |
| `market` | 价格、成交量、流动性等市场事件 |
| `unknown` | 暂无足够证据分类 |

商业推广不等于虚假；分类表达的是传播动机，质量需要结合链上结果评价。

## 6. 证据状态 `evidence_status`

| 值 | 定义 | 能否进入最终结论 |
|---|---|---|
| `verified` | 已从公开页面人工核验核心事实与链接 | 可以，但仍需注明来源限制 |
| `user_supplied` | 用户提供了正文或材料，尚未通过官方 API 重新获取 | 只可作为研究种子 |
| `partial` | URL 或部分事实成立，但正文、时间、CA 等仍有待补证 | 不可单独支撑结论 |
| `unverified` | 待查线索或合成演示 | 不可以 |

`collection_method` 记录“怎么取得”，`evidence_status` 记录“证据到什么程度”；
这两个字段不能混为一谈。

## 7. 聚合特征表 `signal_features`

| 字段 | 含义 |
|---|---|
| `mention_count_15m` | 15 分钟内有效讨论数 |
| `unique_accounts_15m` | 15 分钟内独立账号数 |
| `duplicate_ratio` | 重复/高度相似内容比例 |
| `top5_source_share` | 前五来源占全部讨论的比例 |
| `affiliate_share` | 返佣/推广内容占比 |
| `paid_visibility_flag` | 是否存在可验证付费曝光 |
| `smart_money_buyers_15m` | 15 分钟内高质量钱包买家数 |
| `new_wallet_buyers_15m` | 15 分钟内新钱包买家数 |
| `dev_net_flow_usd_15m` | DEV/关联地址净流入或净流出 |
| `buy_sell_ratio_15m` | 买入笔数与卖出笔数之比 |
| `return_15m/1h/4h` | 信号出现后的区间收益 |
| `mfe_4h` | 4 小时最大有利波动 |
| `mae_4h` | 4 小时最大不利波动/最大回撤 |
| `social_authenticity_score` | 社媒真实性，0–100 |
| `wallet_confirmation_score` | 钱包确认度，0–100 |
| `timeliness_score` | 及时性，0–100 |
| `execution_quality_score` | 流动性/潜在执行质量，0–100 |
| `risk_score` | 风险，0–100，越高风险越大 |
| `user_outcome_score` | 收益友好度，0–100 |

第一版分数规则必须写入代码或配置文件，不能凭感觉手填。

## 8. 数据准确性检查

每次处理自动输出：

- 主键是否唯一
- 必填字段缺失率
- CA 是否符合对应链格式
- 事件时间是否晚于采集时间（异常检查）
- 同一来源是否重复采集
- 数值字段是否出现负流动性等不可能值
- 价格和社媒事件是否使用相同时区
- 聚合结果能否从事件表重新计算
- 随机抽样记录的来源 URL 是否可访问

## 9. 可复现性检查

| 验证方式 | 项目中的对应证据 |
|---|---|
| 随机抽一行 | `source_url`、原始记录、采集时间 |
| 对照链上交易 | `transaction_hash`、wallet、block time |
| 换一个 CA 重跑 | Go 采集参数 + Python 管道参数 |
| 删除/重复一条数据 | 验证脚本和去重规则应触发 |
| 质疑时间顺序 | 统一 UTC，展示原始时区和转换规则 |
| 质疑钱包标签 | 保存标签来源、版本和 `unverified` 状态 |
| 质疑只选上涨案例 | 同时展示成功、混合和风险案例 |

