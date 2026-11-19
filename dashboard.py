"""Continuous decision-oriented Streamlit dashboard."""

from __future__ import annotations

import html
import hmac
import json
import re
from collections import Counter
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from pipeline import load_events

ROOT = Path(__file__).parent
DATA = ROOT / "data"
EVENTS = DATA / "processed/events_verified.csv"
X_POSTS = DATA / "processed/ax1_x_posts.csv"
X_HEAT = DATA / "processed/ax1_social_heat_evidence.json"
X_HOURLY = DATA / "processed/ax1_social_activity_hourly.csv"
AX1_OHLCV = DATA / "processed/ax1_hourly_ohlcv.csv"
MARKET_HEAT = DATA / "processed/ax1_market_heat_benchmark.json"
MARKET_SNAPSHOT = DATA / "manual/ax1_market_snapshot.json"
NIULAI_X_POSTS = DATA / "processed/niulai_x_posts.csv"
NIULAI_X_HEAT = DATA / "processed/niulai_social_heat_evidence.json"
NIULAI_X_SUMMARY = DATA / "processed/niulai_x_collection_summary.json"
NIULAI_X_HOURLY = DATA / "processed/niulai_social_activity_hourly.csv"
NIULAI_OHLCV = DATA / "processed/niulai_hourly_ohlcv.csv"
NIULAI_DAILY = DATA / "processed/niulai_daily_ohlcv_full.csv"
NIULAI_MARKET_SNAPSHOT = DATA / "processed/niulai_market_snapshot.json"
NIULAI_HISTORY = DATA / "manual/niulai_history_evidence.json"

AX1_SAMPLE_SCOPE = "11月11—18日：发射前6日＋发射后18小时的有界样本"
NIULAI_HISTORY_SCOPE = "8月15日至11月18日：分窗采集并完成实体消歧的历史样本"
NIULAI_CURRENT_SCOPE = "11月11—18日：连续近7日样本"


THEME_CSS = """
<style>
:root {
  --canvas: #080b0c;
  --panel: #111618;
  --panel-strong: #171d1f;
  --line: #273033;
  --line-soft: #1c2325;
  --text: #f2f5f3;
  --muted: #8e9996;
  --accent: #d8ff4f;
  --accent-soft: #252d16;
}

.stApp { background: var(--canvas); color: var(--text); }
h1:not(.hero-title-row h1) { display: none; }
header[data-testid="stHeader"] {
  background: rgba(8, 11, 12, .92);
  border-bottom: 1px solid var(--line-soft);
}
.block-container {
  max-width: 1440px;
  padding-top: 2.25rem;
  padding-bottom: 5rem;
}
.case-navigation {
  position: sticky;
  top: 5rem;
  padding: 1.15rem 1rem;
  border: 1px solid var(--line);
  border-radius: 1.15rem;
  background: #0c1011;
}
.case-navigation h3 {
  margin: 0 0 .7rem;
  color: var(--accent);
  font-size: .76rem;
  letter-spacing: .14em;
  text-transform: uppercase;
}
.case-navigation a {
  display: block;
  color: #b4bdb9;
  text-decoration: none;
  line-height: 1.55;
  padding: .34rem 0;
  border-bottom: 1px solid var(--line-soft);
}
.case-navigation a:last-child { border-bottom: 0; }
.case-navigation a:hover { color: var(--accent); }

.decision-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: .7rem;
  margin: 1rem 0 1.35rem;
}
.decision-card {
  min-height: 8.1rem;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: var(--panel);
}
.decision-label {
  color: var(--accent);
  font-size: .7rem;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
.decision-value {
  margin-top: .55rem;
  color: var(--text);
  font-size: .93rem;
  font-weight: 650;
  line-height: 1.55;
}
.final-decision {
  padding: 1.35rem 1.5rem;
  border: 1px solid #46523c;
  border-left: 4px solid var(--accent);
  border-radius: 1rem;
  background: linear-gradient(110deg, #151b17 0%, #101516 100%);
  color: #edf3e7;
  font-size: 1.02rem;
  line-height: 1.8;
}
.final-decision strong { color: var(--accent); }

@media (max-width: 900px) {
  .decision-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 620px) {
  .decision-grid { grid-template-columns: 1fr; }
}

.product-hero {
  padding: 1.4rem 0 2.25rem;
  border-bottom: 1px solid var(--line);
  margin-bottom: 2.2rem;
}
.hero-kicker {
  display: flex;
  align-items: center;
  gap: .55rem;
  color: var(--muted);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .13em;
  text-transform: uppercase;
}
.live-dot {
  width: .52rem;
  height: .52rem;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(216, 255, 79, .09);
}
.hero-title-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-top: 1.1rem;
}
.hero-title-row h1 {
  margin: 0;
  color: var(--text);
  font-size: clamp(2.7rem, 6vw, 5.4rem);
  line-height: .93;
  letter-spacing: -.065em;
  font-weight: 760;
}
.hero-badge {
  flex: 0 0 auto;
  border: 1px solid #414b3b;
  border-radius: 999px;
  padding: .52rem .76rem;
  color: var(--accent);
  background: var(--accent-soft);
  font-size: .7rem;
  font-weight: 800;
  letter-spacing: .1em;
}
.hero-copy {
  max-width: 740px;
  margin: 1.2rem 0 0;
  color: #a7b0ad;
  font-size: 1rem;
  line-height: 1.7;
}
.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: .55rem;
  margin-top: 1.25rem;
}
.hero-meta span {
  padding: .42rem .72rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: #0d1112;
  color: #abb4b1;
  font-size: .76rem;
}

h2, h3, h4 { letter-spacing: -.025em; }
h2 {
  margin-top: .35rem !important;
  font-size: clamp(1.65rem, 3vw, 2.35rem) !important;
}
h4 { color: #dce1df; }
p, li, label, [data-testid="stCaptionContainer"] { line-height: 1.65; }
[data-testid="stCaptionContainer"] { color: var(--muted); }
hr {
  border-color: var(--line-soft) !important;
  margin: 3.6rem 0 1.5rem !important;
}

div[data-testid="stMetric"] {
  min-height: 126px;
  padding: 1rem 1.05rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--panel);
}
div[data-testid="stMetric"] label {
  color: var(--muted);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .04em;
}
div[data-testid="stMetricValue"] {
  color: var(--text);
  font-size: 2rem;
  letter-spacing: -.045em;
}
div[data-testid="stMetricDelta"] { color: var(--accent); }
div[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: var(--line) !important;
  border-radius: 18px !important;
}
div[data-testid="stVegaLiteChart"],
div[data-testid="stDataFrame"],
div[data-testid="stTable"] {
  overflow: hidden;
  padding: .6rem;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: var(--panel);
}
div[data-testid="stAlert"] {
  border: 1px solid var(--line);
  border-left: 3px solid var(--accent);
  border-radius: 14px;
  background: var(--panel) !important;
}
div[data-testid="stAlert"] > div { background: var(--panel) !important; }
div[data-testid="stExpander"] {
  overflow: hidden;
  border: 1px solid var(--line) !important;
  border-radius: 14px !important;
  background: #0d1112;
}
div[data-baseweb="input"],
div[data-baseweb="select"] > div {
  border-color: var(--line) !important;
  border-radius: 12px !important;
  background: var(--panel) !important;
}
div[role="radiogroup"] { gap: .5rem; }
div[role="radiogroup"] label {
  padding: .48rem .85rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel);
}
.stButton > button {
  min-height: 2.8rem;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  color: var(--text);
  font-weight: 750;
}
.stButton > button[kind="primary"] {
  border-color: var(--accent);
  background: var(--accent);
  color: #111500;
}
.stButton > button:hover { border-color: var(--accent); color: var(--accent); }
.stButton > button[kind="primary"]:hover { color: #111500; background: #e2ff7a; }
.stButton > button:disabled,
.stButton > button[kind="primary"]:disabled {
  border-color: var(--line);
  background: #151a18;
  color: #69726f;
  opacity: 1;
}

.cloud { line-height: 2.75rem; }
.chip {
  display: inline-block;
  margin: .2rem .22rem .2rem 0;
  padding: .24rem .72rem;
  border: 1px solid #384135;
  border-radius: 999px;
  background: var(--accent-soft);
  color: #e2f99a;
  font-weight: 680;
}
.chip small {
  margin-left: .28rem;
  color: #87936d;
  font-size: .72em;
}

@media (max-width: 760px) {
  .block-container { padding-top: 1rem; }
  .hero-title-row { align-items: flex-start; flex-direction: column; }
  .hero-title-row h1 { font-size: 3rem; }
  .hero-badge { order: -1; }
  div[data-testid="stMetric"] { min-height: 108px; }
}
</style>
"""


@st.cache_data
def load_posts() -> pd.DataFrame:
    frame = pd.read_csv(X_POSTS, dtype={"post_id": "string", "author_id": "string"})
    frame["created_at_utc"] = pd.to_datetime(
        frame["created_at_utc"], utc=True, errors="coerce", format="mixed"
    )
    return frame


@st.cache_data
def load_niulai_posts() -> pd.DataFrame:
    frame = pd.read_csv(NIULAI_X_POSTS, dtype={"post_id": "string", "author_id": "string"})
    frame["created_at_utc"] = pd.to_datetime(
        frame["created_at_utc"], utc=True, errors="coerce", format="mixed"
    )
    return frame[frame["entity_match"].isin(["explicit", "contextual"])].copy()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def bjt(value: object) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    return stamp.tz_convert("Asia/Shanghai").strftime("%Y-%m-%d %H:%M")


def anchor(name: str) -> None:
    st.markdown(f'<span id="{name}"></span>', unsafe_allow_html=True)


def decision_cards(items: list[tuple[str, str]]) -> None:
    cards = "".join(
        '<div class="decision-card">'
        f'<div class="decision-label">{html.escape(label)}</div>'
        f'<div class="decision-value">{html.escape(value)}</div>'
        "</div>"
        for label, value in items
    )
    st.markdown(f'<div class="decision-grid">{cards}</div>', unsafe_allow_html=True)


def final_decision(text: str) -> None:
    st.markdown(
        f'<div class="final-decision"><strong>最终判断</strong><br>{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def secret_value(name: str) -> str:
    """Read an optional Streamlit secret without breaking local/read-only deployments."""

    try:
        return str(st.secrets.get(name, "")).strip()
    except (FileNotFoundError, KeyError):
        return ""


def render_ca_workspace() -> None:
    """Show the reusable CA workflow while keeping paid collection admin-only."""

    anchor("ca-workspace")
    st.subheader("输入代币 CA，查看近 7 日社媒分析")
    ca_col, chain_col, window_col = st.columns([2.4, 1, 1])
    with ca_col:
        ca = st.text_input(
            "代币合约地址（CA）",
            placeholder="粘贴完整的代币合约地址",
            help="CA 用于锁定目标代币，降低同名币和错误合约混入结果的风险。",
        ).strip()
    with chain_col:
        st.selectbox("链", ["自动识别", "Base", "BNB Chain", "Solana", "Ethereum"])
    with window_col:
        st.selectbox("观察窗口", ["近 7 日"], disabled=True)

    st.info(
        "受 X API Token 额度限制，在线查询仅限管理员使用。"
        "请向下浏览 AX1 与 NIULAI 社媒分析案例，了解产品功能。"
    )

    stored_code = secret_value("ADMIN_ACCESS_CODE")
    live_enabled = secret_value("LIVE_CA_ANALYSIS_ENABLED").lower() == "true"
    with st.expander("管理员采集控制台"):
        st.caption("管理员口令只保存在 Streamlit Secrets，不写入代码或公开仓库。")
        access_code = st.text_input("管理员口令", type="password", key="admin_access_code")
        if st.button("验证管理员", key="verify_admin"):
            if not stored_code:
                st.warning("当前为公开演示模式，尚未在云端配置管理员口令。")
            elif hmac.compare_digest(access_code, stored_code):
                st.session_state["admin_authenticated"] = True
                st.success("管理员身份已验证。")
            else:
                st.session_state["admin_authenticated"] = False
                st.error("口令不正确。")
        is_admin = bool(st.session_state.get("admin_authenticated"))
        can_run = is_admin and live_enabled
        if st.button(
            "生成近 7 日社媒观察",
            type="primary",
            disabled=not can_run,
            key="run_ca_analysis",
        ):
            if not ca:
                st.error("请先输入 CA。")
            else:
                st.info("实时采集任务入口已就绪；后台采集与缓存服务将在下一版本接入。")
        if is_admin and not live_enabled:
            st.info("管理员已登录，但实时采集服务开关尚未启用。")
        elif not is_admin:
            st.caption("当前为访客只读模式。管理员验证且服务开关开启后，采集按钮才会启用。")


def normalise(value: object) -> str:
    value = str(value).lower()
    value = re.sub(r"https?://\S+|@[\w_]+|0x[a-f0-9]+|\$\w+|\d+(?:\.\d+)?[kmb]?", " ", value)
    return " ".join(re.sub(r"[^a-z\u4e00-\u9fff ]", " ", value).split())


def enrich(posts: pd.DataFrame) -> pd.DataFrame:
    frame = posts.copy()
    text = frame["text"].fillna("").str.lower()
    norm = frame["text"].map(normalise)
    campaign = text.str.contains(
        r"coinmarketcap|leaderboard|\bvote(?:s|d|ing)?\b|giveaway|trading comp", regex=True
    )
    low_info = norm.str.fullmatch(
        r"(?:all )?done|thanks for the mention|support|agreed|nice|great|gm|lfg|lets go"
    ).fillna(False)
    risk = text.str.contains(
        r"\brisk|concern|unclear|hidden|blacklist|honeypot|rug|needs? (?:clear|proof)|not enough|sell pressure|warning",
        regex=True,
    )
    callout = text.str.contains(
        r"\b(?:buy|ape|aped|send it|entry|gem|moon|don.t fade|load up|bullish)\b", regex=True
    )
    product = text.str.contains(
        r"\b(?:agent|agents|agentic|console|x402|autopilot|assay|utility|adoption)\b", regex=True
    )
    frame["speech_act"] = "一般讨论"
    frame.loc[product, "speech_act"] = "产品/事实解释"
    frame.loc[callout, "speech_act"] = "交易号召"
    frame.loc[risk, "speech_act"] = "风险质疑"
    frame.loc[low_info, "speech_act"] = "低信息回应"
    frame.loc[campaign, "speech_act"] = "活动动员"
    positive = text.str.contains(
        r"\b(?:bullish|buy|ape|gem|moon|great|good|strong|love|excited|win|send it)\b", regex=True
    )
    frame["stance"] = "中性/信息"
    frame.loc[positive, "stance"] = "偏多/支持"
    frame.loc[risk, "stance"] = "谨慎/质疑"
    repeats = norm[norm.ne("") & norm.duplicated(False)]
    frame["repeated"] = norm.isin(set(repeats))
    frame["campaign"] = campaign
    return frame


def enrich_niulai(posts: pd.DataFrame) -> pd.DataFrame:
    frame = posts.copy()
    text = frame["text"].fillna("").str.lower()
    norm = frame["text"].map(normalise)
    positive = text.str.contains(
        r"看好|买入|抄底|持仓|上车|牛市|涨|目标|支持|buy|bullish|hold|gem|moon", regex=True
    )
    cautious = text.str.contains(
        r"风险|亏|跌|回撤|卖出|清仓|割|不买|不追|risk|bear|sell|rug", regex=True
    )
    callout = text.str.contains(r"买入|抄底|上车|冲|目标|buy|ape|entry|gem|moon", regex=True)
    market_fact = text.str.contains(
        r"市值|价格|成交|流动性|持仓|钱包|聪明钱|holder|mcap|market cap|volume|liquidity|price",
        regex=True,
    )
    exchange = text.str.contains(r"币安|binance|kucoin|gate|mexc|上市|上所", regex=True)
    frame["stance"] = "中性/信息"
    frame.loc[positive, "stance"] = "偏多/支持"
    frame.loc[cautious, "stance"] = "谨慎/看空"
    frame.loc[positive & cautious, "stance"] = "多空并存"
    frame["speech_act"] = "一般讨论"
    frame.loc[exchange, "speech_act"] = "交易所与市场预期"
    frame.loc[market_fact, "speech_act"] = "行情/钱包信息"
    frame.loc[callout, "speech_act"] = "交易行动表达"
    frame.loc[cautious, "speech_act"] = "风险与离场表达"
    frame["automated_alert"] = text.str.contains(r"coinwings|smart money alert|聪明钱动态|鲸鱼信号", regex=True)
    repeats = norm[norm.ne("") & norm.duplicated(False)]
    frame["repeated"] = norm.isin(set(repeats))
    return frame


def niulai_topic_table(posts: pd.DataFrame) -> pd.DataFrame:
    text = posts["text"].fillna("").str.lower()
    rules = [
        ("价格、市值与涨跌", r"价格|市值|涨|跌|回撤|倍|price|market cap|mcap|pump|ath"),
        ("交易、持仓与抄底", r"抄底|持仓|仓位|买入|上车|现货|交易|buy|hold|entry|ape|冲"),
        ("币安与交易所预期", r"币安|binance|kucoin|gate|mexc|上市|上所|合约"),
        ("风险与离场", r"风险|亏|割|卖|清仓|回撤|sell|risk|bear|rug|控盘"),
        ("中文Meme与社区身份", r"中文|华语|meme|社区|牛市|community|culture|ip"),
        ("聪明钱与钱包", r"聪明钱|钱包|smart money|wallet|控盘|大户|holder"),
    ]
    rows = []
    for name, rule in rules:
        mask = text.str.contains(rule, regex=True)
        rows.append([name, int(mask.sum()), int(posts.loc[mask, "author_id"].nunique()), float(mask.mean())])
    return pd.DataFrame(rows, columns=["社区主要话题", "相关帖子", "涉及作者", "占有效帖子"]).sort_values(
        "相关帖子", ascending=False
    )


def topic_chips(topics: pd.DataFrame) -> None:
    largest = max(int(value) for value in topics["相关帖子"])
    chips = [
        f'<span class="chip" style="font-size:{.85 + .85 * int(row["相关帖子"]) / largest:.2f}rem">'
        f'{html.escape(str(row["社区主要话题"]))} <small>{int(row["相关帖子"])}</small></span>'
        for _, row in topics.iterrows()
    ]
    st.markdown('<div class="cloud">' + "".join(chips) + "</div>", unsafe_allow_html=True)


def topic_table(posts: pd.DataFrame) -> pd.DataFrame:
    text = posts["text"].fillna("").str.lower()
    rules = [
        ("Base / Clanker / 发射", r"\b(?:base|clanker|launch|contract|token|ca)\b|0x[0-9a-f]{6,}"),
        ("AI Agent / X402 / 产品使用", r"\b(?:ai|agent|agents|agentic|x402|console|autopilot|utility|adoption|payment)\b"),
        ("供应、钱包与链上风险", r"\b(?:liquidity|holder|burn|dev|supply|tax|wallet|sniper|bundle|rug|risk)\b"),
        ("社区活动与任务", r"\b(?:done|support|community|quest|giveaway|vote|leaderboard|task)\b"),
        ("价格与交易行动", r"\b(?:buy|sell|entry|send it|moon|gem|market cap|price|trade|pump)\b"),
    ]
    rows = []
    for name, rule in rules:
        mask = text.str.contains(rule, regex=True)
        rows.append([name, int(mask.sum()), int(posts.loc[mask, "author_id"].nunique()), float(mask.mean())])
    return pd.DataFrame(rows, columns=["社区主要话题", "相关帖子", "涉及作者", "占全部帖子"]).sort_values(
        "相关帖子", ascending=False
    )


def keyword_cloud(posts: pd.DataFrame) -> None:
    stop = set(
        "the a an and or to of in on for is are was were be this that it with from at by as we you i they our your not but have has can would will just so if than into about out up all get more very now new ax1 axbot every one here part even under".split()
    )
    aliases = {"agents": "agent", "agentic": "agent", "votes": "vote", "voting": "vote", "launched": "launch", "launching": "launch", "payments": "payment"}
    counts: Counter[str] = Counter()
    for value in posts["text"].fillna(""):
        clean = re.sub(r"https?://\S+|@[\w_]+|0x[a-fA-F0-9]+|\$\w+", " ", value.lower())
        for word in re.findall(r"[a-z][a-z0-9'-]{2,}", clean):
            word = aliases.get(word, word)
            if word not in stop:
                counts[word] += 1
    words = counts.most_common(14)
    largest = max(count for _, count in words)
    chips = [
        f'<span class="chip" style="font-size:{.85 + .85 * count / largest:.2f}rem" title="{count}次">{html.escape(word)} <small>{count}</small></span>'
        for word, count in words
    ]
    st.markdown('<div class="cloud">' + "".join(chips) + "</div>", unsafe_allow_html=True)


def load_hourly_market(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["hour_utc"] = pd.to_datetime(frame["hour_utc"], utc=True, format="mixed")
    frame["hour_bjt"] = frame["hour_utc"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return frame.sort_values("hour_utc")


def phase_market(market: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> str:
    part = market[market["hour_utc"].ge(start.floor("h")) & market["hour_utc"].lt(end)]
    if part.empty:
        return "上池前，无价格与成交数据"
    opening, closing = float(part.iloc[0].open_usd), float(part.iloc[-1].close_usd)
    peak, volume = float(part.high_usd.max()), float(part.volume_usd.sum())
    return f"成交 ${volume:,.0f}；阶段收盘 {(closing/opening-1)*100:+,.1f}%；最高 {(peak/opening-1)*100:+,.1f}%"


def phase_table(posts: pd.DataFrame, market: pd.DataFrame) -> pd.DataFrame:
    launch = pd.Timestamp("2026-11-17T15:37:05Z")
    specs = [
        (pd.Timestamp("1900-01-01", tz="UTC"), launch, "发射前关注", "AI Agent、X402、Autopilot与TGE预告"),
        (launch, pd.Timestamp("2026-11-17T18:00Z"), "上池 / 发射", "合约、供应销毁、Base/Clanker与买入"),
        (pd.Timestamp("2026-11-17T18:00Z"), pd.Timestamp("2026-11-18T00:00Z"), "交易传播扩散", "产品解释、价格讨论、转发与活动"),
        (pd.Timestamp("2026-11-18T00:00Z"), pd.Timestamp("2100-01-01", tz="UTC"), "社区活动延续", "CMC投票、任务回复、持币与产品采用"),
    ]
    rows = []
    for start, end, stage, content in specs:
        part = posts[posts.created_at_utc.ge(start) & posts.created_at_utc.lt(end)]
        evidence = phase_market(market, start, end)
        if stage == "发射前关注":
            pre24 = part[part.created_at_utc.ge(launch - pd.Timedelta(hours=24))]
            evidence = f"上池前24h已有 {len(pre24)} 帖 / {pre24.author_id.nunique()} 作者"
        rows.append([f"{bjt(part.created_at_utc.min())} — {bjt(part.created_at_utc.max())}", stage, f"{len(part)} / {part.author_id.nunique()}", content, evidence])
    return pd.DataFrame(rows, columns=["时间（北京时间）", "阶段", "帖子 / 作者", "主要内容", "市场数据与判断"])


def market_chart(market_path: Path = AX1_OHLCV, social_path: Path = X_HOURLY) -> None:
    market = load_hourly_market(market_path)
    market["方向"] = market.close_usd.ge(market.open_usd).map({True: "上涨", False: "下跌"})
    x = alt.X("hour_bjt:T", title="北京时间", axis=alt.Axis(format="%m-%d %H:%M", tickCount=8, labelAngle=0))
    color = alt.Color("方向:N", scale=alt.Scale(domain=["上涨", "下跌"], range=["#ff9255", "#d8ff4f"]))
    wick = alt.Chart(market).mark_rule().encode(x=x, y=alt.Y("low_usd:Q", title="价格USD", scale=alt.Scale(zero=False)), y2="high_usd:Q", color=color)
    body = alt.Chart(market).mark_bar(size=10).encode(x=x, y=alt.Y("open_usd:Q", scale=alt.Scale(zero=False)), y2="close_usd:Q", color=color)
    social = pd.read_csv(social_path)
    social["hour_bjt"] = pd.to_datetime(social.hour_utc, utc=True, format="mixed").dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    social = social[social.hour_bjt.between(market.hour_bjt.min(), market.hour_bjt.max())]
    bars = alt.Chart(social).mark_bar(color="#d8ff4f", opacity=.72).encode(x=x, y=alt.Y("post_count:Q", title="帖子数"), tooltip=["hour_bjt:T", "post_count:Q", "unique_authors:Q"])
    line = alt.Chart(social).mark_line(color="#ff9255", point=True).encode(x=x, y=alt.Y("unique_authors:Q", title="作者数"))
    st.altair_chart(alt.vconcat((wick + body).properties(height=250), (bars + line).resolve_scale(y="independent").properties(height=175)).resolve_scale(x="shared"), width="stretch")


def case_navigation(token: str) -> None:
    if token == "AX1":
        items = [
            ("ax1-summary", "1. 现在发生什么"),
            ("ax1-persona", "2. 谁在参与"),
            ("ax1-market", "3. 社媒与价格"),
            ("ax1-risk", "4. 风险闸门"),
            ("ax1-decision", "5. 最终判断"),
            ("ax1-benchmark", "6. 指标口径"),
            ("ax1-evidence", "7. 原始证据"),
        ]
    else:
        items = [
            ("niulai-summary", "1. 现在发生什么"),
            ("niulai-persona", "2. 谁在参与"),
            ("niulai-market", "3. 社媒与价格"),
            ("niulai-onchain", "4. 风险闸门"),
            ("niulai-decision", "5. 最终判断"),
            ("niulai-benchmark", "6. 指标口径"),
            ("niulai-evidence", "7. 原始证据"),
        ]
    links = "".join(f'<a href="#{target}">{label}</a>' for target, label in items)
    st.markdown(
        f'<nav class="case-navigation"><h3>{token} 案例目录</h3>{links}</nav>',
        unsafe_allow_html=True,
    )


def render_ax1() -> None:
    posts = enrich(load_posts())
    heat, snapshot, market = read_json(X_HEAT), read_json(MARKET_SNAPSHOT), load_hourly_market(AX1_OHLCV)
    att = heat["social_attention"]
    latest = posts.created_at_utc.max()
    topics = topic_table(posts)
    campaign, repeated = posts.campaign.mean(), posts.repeated.mean()
    anchor("ax1-summary"); st.header("AX1：现在发生什么？")
    st.info("**一句话：社区讨论核心是“AI Agent实际使用 + Base/Clanker发射”，表达整体偏支持；但CMC投票和活动动员占据可见份额，不能把帖子增长全部解释为自然讨论。**")
    decision_cards([
        ("讨论规模", f"{len(posts)}帖 · {posts.author_id.nunique()}位作者"),
        ("主要参与者", "Base / Clanker 新币关注者与 AI Agent 产品关注者"),
        ("社媒 × 价格", "发射阶段同向上涨；传播扩散阶段价格回撤21.2%"),
        ("关键风险", f"活动动员{campaign:.1%} · 相似/重复文本{repeated:.1%}"),
    ])
    cols = st.columns(5)
    vals = [("有效帖子", len(posts)), ("独立作者", posts.author_id.nunique()), ("近24h帖子", len(posts[posts.created_at_utc.ge(latest-pd.Timedelta(hours=24))])), ("活动动员内容", f"{campaign:.1%}"), ("相似/重复文本", f"{repeated:.1%}")]
    for col, (label, value) in zip(cols, vals): col.metric(label, value)
    st.markdown("#### 一眼看懂社区在谈什么"); keyword_cloud(posts)
    st.success("**社区关键词总结：** " + " · ".join(topics.head(3)["社区主要话题"]))

    st.divider(); anchor("ax1-persona"); st.header("谁正在参与AX1讨论？")
    callouts = posts[posts.matched_query_ids.fillna("").str.contains("callouts", regex=False)]
    groups = [
        ["AI Agent / 产品关注者", posts[posts.text.str.contains(r"agent|x402|console|autopilot", case=False, regex=True)].author_id.nunique(), "产品与真实使用"],
        ["Base / Clanker新币关注者", posts[posts.text.str.contains(r"base|clanker|launch", case=False, regex=True)].author_id.nunique(), "发射、合约与交易启动"],
        ["投票与活动参与者", posts.loc[posts.campaign, "author_id"].nunique(), f"活动内容占{campaign:.1%}"],
        ["交易号召关注者", callouts.author_id.nunique(), f"喊单查询轨{len(callouts)}帖"],
        ["风险审查者", posts[posts.speech_act.eq("风险质疑")].author_id.nunique(), "供应、钱包与采用质疑"],
    ]
    st.dataframe(pd.DataFrame(groups, columns=["参与者类型", "涉及作者", "文本证据"]), width="stretch", hide_index=True)
    st.info("**画像结论：** 产品关注、交易关注和活动参与同时存在，应分开观察；“只出现一次”本身不用于判断社区黏性。")

    st.divider(); anchor("ax1-text"); st.header("社区话题、表达倾向与传播功能")
    st.dataframe(topics, width="stretch", hide_index=True, column_config={"占全部帖子": st.column_config.ProgressColumn(format="percent")})
    left, right = st.columns(2)
    with left: st.markdown("#### 表达倾向"); st.bar_chart(posts.stance.value_counts().rename("帖子数"))
    with right: st.markdown("#### 传播功能"); st.bar_chart(posts.speech_act.value_counts().rename("帖子数"))
    st.success("**语言信号：产品解释 + 发射信息 + 活动动员。** “偏支持”同时包含真实产品讨论、交易号召和投票任务，不能只用一个情绪分数概括。")

    st.divider(); anchor("ax1-phase"); st.header("传播阶段与市场变化")
    st.dataframe(phase_table(posts, market), width="stretch", hide_index=True)
    st.info("**数据结论：** 上池前24小时已有17帖、13名作者；上池阶段成交约105万美元，阶段收盘相对首根小时K开盘约+14,714%。随后社媒继续扩散，但交易传播阶段价格约回撤21.2%，说明热度增加不等于价格继续上涨。")

    st.divider(); anchor("ax1-market"); st.header("社媒与价格是否同步？")
    market_chart()
    first, last, volume = market.iloc[0].open_usd, market.iloc[-1].close_usd, market.volume_usd.sum()
    cols = st.columns(4)
    for col, item in zip(cols, [("起点价格", f"${first:.6f}"), ("最新小时收盘", f"${last:.5f}"), ("区间变化", f"{last/first-1:+,.1%}"), ("区间成交", f"${volume:,.0f}")]): col.metric(*item)
    st.warning("社媒峰值与价格变化同步只能说明时间相关，还需要更多事件样本才能讨论因果。")

    st.divider(); anchor("ax1-risk"); st.header("交易前还要通过哪些风险闸门？")
    cols = st.columns(5)
    for col, item in zip(cols, [("Top 10", snapshot["holdings"]["top10"]), ("DEV", snapshot["holdings"]["dev"]), ("老鼠仓", snapshot["holdings"]["insider"]), ("捆绑地址", snapshot["holdings"]["bundle"]), ("持币地址", snapshot["market"]["holders"])]): col.metric(*item)
    risks = [
        ["持仓结构", "第三方快照", "Top10 20%；DEV 0；老鼠仓<0.1%；捆绑地址0"],
        ["聪明钱", "部分完成", "第三方标签显示聪明钱(4/8)、KOL(3)、狙击(1)；钱包历史待核验"],
        ["可卖性与权限", "待补官方风险报告", "页面基础安全标签不能替代黑名单/Mint/管理员逐项检查"],
        ["社媒真实性", "部分完成", f"活动动员{campaign:.1%}；相似/重复{repeated:.1%}，含正常转发"],
        ["执行质量", "部分完成", f"流动性{snapshot['market']['liquidity']}；24h成交{snapshot['market']['volume_24h']}；净买入{snapshot['market']['net_volume']}；滑点/MEV待测"],
    ]
    st.dataframe(pd.DataFrame(risks, columns=["风险层", "证据状态", "AX1当前证据"]), width="stretch", hide_index=True)
    st.divider(); anchor("ax1-decision"); st.header("AX1最终判断")
    final_decision(
        "AX1存在真实的产品与发射讨论，并非只有机器播报；但当前声量同时混入活动动员和重复传播。"
        "发射阶段社媒与价格同向，传播继续扩散后价格却回撤，说明热度尚未转化为持续买盘。"
        "更适合继续观察新增独立作者、产品采用和回访钱包；在权限与钱包历史补齐前，不把社媒热度单独当作交易信号。"
    )

    st.divider(); anchor("ax1-benchmark"); st.header("指标校准与对照")
    st.info("“只发1条的作者占比”只描述参与广度，不能单独证明社区黏性弱；必须与相同币龄、采集窗口和查询结构的样本比较。")
    niu = read_json(NIULAI_X_HEAT)["social_attention"]
    benchmark = [
        ["AX1", f"{len(posts):,}", f"{posts.author_id.nunique():,}", f"{att['single_post_author_share']:.1%}", f"{att['top_10_author_post_share']:.1%}", f"{att['original_share']:.1%}", AX1_SAMPLE_SCOPE],
        ["NIULAI", f"{niu['unique_posts']:,}", f"{niu['unique_authors']:,}", f"{niu['single_post_author_share']:.1%}", f"{niu['top_10_author_post_share']:.1%}", f"{niu['original_share']:.1%}", NIULAI_HISTORY_SCOPE],
        ["TRUMP", "—", "—", "—", "—", "—", "尚未按相同规则采集"],
    ]
    st.dataframe(pd.DataFrame(benchmark, columns=["代币", "帖子", "作者", "只出现1次作者", "Top10作者占比", "原创占比", "样本范围"]), width="stretch", hide_index=True)
    st.info("这张表只比较讨论结构，不比较绝对热度；只有币龄、观察窗口和查询规则一致时，帖子总量才具有直接可比性。")

    st.divider(); anchor("ax1-evidence"); st.header("原始证据与分析口径")
    st.markdown("- X：官方API有界采集，保留Raw JSON并按post_id去重。\n- 市场：GeckoTerminal小时OHLCV；底层统一UTC。\n- 链上指标：带时间戳的第三方人工快照，动态值需重新核验。\n- 文本：可解释规则分类，不把标签当事实。")
    with st.expander("低优先级指标与原始帖子"):
        cols = st.columns(4)
        values = [("互动中位数", att["interaction_median"]), ("互动P90", att["interaction_p90"]), ("Top10作者占比", f"{att['top_10_author_post_share']:.1%}"), ("市场活跃度", f"P{read_json(MARKET_HEAT)['calibration']['market_activity_score_0_100']:.1f}")]
        for col, item in zip(cols, values): col.metric(*item)
        st.dataframe(posts.sort_values("created_at_utc", ascending=False)[["created_at_utc", "post_type", "text", "lang", "total_interactions", "source_url"]].head(200), width="stretch", hide_index=True, column_config={"source_url": st.column_config.LinkColumn("原帖", display_text="打开")})


def render_niulai(events: pd.DataFrame) -> None:
    history_posts = enrich_niulai(load_niulai_posts())
    recent_start = pd.Timestamp("2026-11-11T13:00:00Z")
    posts = enrich_niulai(history_posts[history_posts.created_at_utc.ge(recent_start)])
    summary, history = read_json(NIULAI_X_SUMMARY), read_json(NIULAI_HISTORY)
    snapshot, market = read_json(NIULAI_MARKET_SNAPSHOT), load_hourly_market(NIULAI_OHLCV)
    topics, latest = niulai_topic_table(posts), posts.created_at_utc.max()
    selected = events[events.token_symbol.eq("NIULAI")].copy()
    current_return = market.iloc[-1].close_usd / market.iloc[0].open_usd - 1

    anchor("niulai-summary"); st.header("NIULAI：现在发生什么？")
    st.info("**完整故事：电影先因‘粗糙、荒诞、妈妈梗’在Web2反向走红；加密玩家再把‘牛来＝牛市来了’翻译成Ticker和合约；价格、KOL盈利截图与交易所入口反向制造更多注意力。三个月后，讨论仍在，但已转为回撤中的持仓、抄底和交易所预期。**")
    decision_cards([
        ("当前讨论规模", f"近7日{len(posts)}帖 · {posts.author_id.nunique()}位作者"),
        ("主要参与者", "价格/波段关注者、现货持有者与交易所预期关注者"),
        ("社媒 × 价格", f"讨论持续，但近7日价格{current_return:+.1%}"),
        ("关键风险", f"机器播报{posts.automated_alert.mean():.1%} · 持仓数据存在来源冲突"),
    ])
    cols = st.columns(5)
    values = [("历史有效样本", len(history_posts)), ("历史独立作者", history_posts.author_id.nunique()), ("近7日有效帖子", len(posts)), ("近7日机器播报", f"{posts.automated_alert.mean():.1%}"), ("近7日价格", f"{current_return:+.1%}")]
    for col, item in zip(cols, values): col.metric(*item)
    st.markdown("#### 一眼看懂当前社区在谈什么"); topic_chips(topics.head(6))
    st.success("**当前社区总结：价格与涨跌 · 持仓/抄底 · 币安预期；情绪不是单边看多，而是回撤中的分歧交易。**")

    st.divider(); anchor("niulai-persona"); st.header("谁正在参与NIULAI讨论？")
    text = posts.text.fillna("").str.lower()
    persona_rules = [("价格/波段关注者", r"价格|市值|涨|跌|回撤|倍|price|mcap|ath", "讨论涨跌、价格与市值"), ("现货持有与抄底者", r"抄底|持仓|仓位|买入|上车|现货|buy|hold", "表达持仓、买入或抄底计划"), ("交易所预期关注者", r"币安|binance|kucoin|gate|mexc|上市|上所", "把上所和交易所支持作为预期"), ("聪明钱/钱包信号用户", r"聪明钱|钱包|smart money|wallet|大户|holder", "关注链上钱包动作；含自动播报"), ("风险与离场讨论者", r"风险|亏|跌|回撤|卖出|清仓|割|不追|risk|bear|sell", "讨论回撤、卖出与风险")]
    personas = []
    for label, rule, evidence in persona_rules:
        mask = text.str.contains(rule, regex=True)
        personas.append([label, int(mask.sum()), int(posts.loc[mask, "author_id"].nunique()), evidence])
    st.dataframe(pd.DataFrame(personas, columns=["参与者类型", "相关帖子", "涉及作者", "文本证据"]), width="stretch", hide_index=True)
    st.info("**画像结论：** 当前是已进入二级市场的中文Meme社区；早期进入者交易的是电影热搜与链上资产之间的时间差，当前用户交易的是回撤、持仓和平台预期。")

    st.divider(); anchor("niulai-text"); st.header("社区话题、表达倾向与传播功能")
    st.dataframe(topics, width="stretch", hide_index=True, column_config={"占有效帖子": st.column_config.ProgressColumn(format="percent")})
    left, right = st.columns(2)
    with left: st.markdown("#### 表达倾向"); st.bar_chart(posts.stance.value_counts().rename("帖子数"))
    with right: st.markdown("#### 文本功能"); st.bar_chart(posts.speech_act.value_counts().rename("帖子数"))
    st.warning(f"**实体消歧：** 855条去重历史与近期帖子中保留{len(history_posts)}条明确或有上下文指向目标合约的内容；另有{summary['ambiguous_or_wrong_contract_posts']}条同名币、其他CA或泛用短语被排除。")
    st.success("**传播学结论：** 37条近期CoinWings多语言自动播报由4个账号产生，能放大可见声量，但不能等同于37次独立社区判断。")

    st.divider(); anchor("niulai-phase"); st.header("完整发酵链路")
    stages = [
        ["08-05—08-13", history["stages"][0]["stage"], "0 / 0", history["stages"][0]["summary"], history["stages"][0]["market_fact"], "Web2先发生，X加密样本尚未出现"],
        ["08-13—08-16", history["stages"][1]["stage"], "8 / 8", history["stages"][1]["summary"], history["stages"][1]["market_fact"], "8月15日晚样本已出现50K→数百倍、20M市值与钱包提醒"],
        ["08-16—08-19", history["stages"][2]["stage"], "采样缺口", history["stages"][2]["summary"], history["stages"][2]["market_fact"], "用有日期媒体复盘补足短视频、KOL与价格反馈循环"],
        ["08-19—09-01", history["stages"][3]["stage"], "120 / 109", history["stages"][3]["summary"], history["stages"][3]["market_fact"], "X出现全球二创、100M目标、上币投票、合约和交易竞赛"],
        ["09-01—11-01", "高位换手与社区维持", "190 / 112", "价格、交易所预期与官方运营成为主要内容。", "爆发期结束，但社媒和交易没有归零。", "按月封顶样本，不能用数量比较月度热度"],
        ["11-01—11-18", history["stages"][4]["stage"], "226 / 162", history["stages"][4]["summary"], history["stages"][4]["market_fact"], "近7日连续窗口可用于当前结构判断"],
    ]
    st.dataframe(pd.DataFrame(stages, columns=["时间", "阶段", "X样本 帖子/作者", "发生了什么", "市场/外部证据", "数据限制"]), width="stretch", hide_index=True)
    st.info("**发酵机制：Web2猎奇围观 → 加密圈完成Ticker/合约翻译 → KOL和早期收益验证 → 价格与盈利截图反向扩散 → 交易所降低参与门槛 → 热点退潮后转为存量持仓社区。**")

    st.divider(); anchor("niulai-market"); st.header("社媒与价格是否同步？")
    daily = pd.read_csv(NIULAI_DAILY); daily["date_utc"] = pd.to_datetime(daily.date_utc, utc=True).dt.tz_localize(None)
    line = alt.Chart(daily).mark_line(color="#d8ff4f", strokeWidth=2).encode(x=alt.X("date_utc:T", title="UTC日期", axis=alt.Axis(format="%m-%d")), y=alt.Y("close_usd:Q", title="日收盘价USD", scale=alt.Scale(zero=False)), tooltip=[alt.Tooltip("date_utc:T", title="日期"), alt.Tooltip("close_usd:Q", title="收盘", format=".5f"), alt.Tooltip("volume_usd:Q", title="成交", format=",.0f")])
    events_df = pd.DataFrame({"date_utc": pd.to_datetime(["2026-08-15", "2026-08-18", "2026-08-30"]), "事件": ["X早期链上样本", "Binance Alpha阶段", "Binance合约公告"]})
    markers = alt.Chart(events_df).mark_rule(color="#ff9255", strokeDash=[4, 3]).encode(x="date_utc:T", tooltip=["事件:N"])
    st.altair_chart((line + markers).properties(height=300), width="stretch")
    st.caption("主池日线从8月15日开始；更早迁移市值使用有日期的外部复盘，不把不同池价格强行拼接。历史X按窗口封顶，因此不画成连续热度曲线。")
    st.markdown("#### 当前近7日：连续社媒窗口 × 小时K线")
    social_window = pd.read_csv(NIULAI_X_HOURLY)
    social_window["hour_utc"] = pd.to_datetime(social_window["hour_utc"], utc=True, format="mixed")
    market_start = pd.to_datetime(market.iloc[0].hour_utc, utc=True)
    market_end = pd.to_datetime(market.iloc[-1].hour_utc, utc=True)
    social_window = social_window[social_window.hour_utc.between(market_start, market_end)]
    peak_social = social_window.loc[social_window.post_count.idxmax()]
    peak_social_bjt = peak_social.hour_utc.tz_convert("Asia/Shanghai").strftime("%m月%d日 %H:%M")
    window_return = current_return
    peak_to_end = market.iloc[-1].close_usd / market.high_usd.max() - 1
    st.info(
        f"**近7日联动结论：** 价格累计{window_return:+.1%}，从区间最高点回撤{abs(peak_to_end):.1%}；"
        f"同窗口记录{int(social_window.post_count.sum())}帖。发帖峰值出现在{peak_social_bjt}，"
        f"单小时{int(peak_social.post_count)}帖但仅{int(peak_social.unique_authors)}名作者，"
        "说明当前声量存在集中放大，尚未形成由大量新增作者推动、并带动价格反转的扩散信号。"
    )
    market_chart(NIULAI_OHLCV, NIULAI_X_HOURLY)
    first, last, volume = market.iloc[0].open_usd, market.iloc[-1].close_usd, market.volume_usd.sum()
    cols = st.columns(5)
    for col, item in zip(cols, [("起点价格", f"${first:.5f}"), ("最新小时收盘", f"${last:.5f}"), ("区间变化", f"{last/first-1:+.1%}"), ("区间成交", f"${volume:,.0f}"), ("主池流动性", f"${snapshot['liquidity_usd']:,.0f}")]): col.metric(*item)

    st.divider(); anchor("niulai-onchain"); st.header("交易前还要通过哪些风险闸门？")
    tx = snapshot["transactions_24h"]
    risks = [["持仓结构", "存在冲突", "Top10旧快照85.11%与30.4%冲突；需通过独立链上来源重新核验托管/池子地址"], ["聪明钱", "未验证", "X出现钱包播报，但没有可审计的历史胜率、成本与是否已卖出路径"], ["可卖性与权限", "项目方声明，待链上核验", "项目称放弃所有权、不可增发、LP销毁、买卖税1%；旧审计来源与LP声明冲突"], ["社媒真实性", "部分完成", f"近7日机器播报{posts.automated_alert.mean():.1%}；重复/相似文本{posts.repeated.mean():.1%}；全历史排除同名/错误CA {summary['ambiguous_or_wrong_contract_posts']}条"], ["执行质量", "市场数据已补，滑点待测", f"主池流动性${snapshot['liquidity_usd']:,.0f}；24h成交${snapshot['volume_24h_usd']:,.0f}；买{tx['buys']}笔/卖{tx['sells']}笔/独立交易者{tx['unique_traders']}"]]
    st.dataframe(pd.DataFrame(risks, columns=["风险层", "证据状态", "NIULAI当前证据"]), width="stretch", hide_index=True)

    st.divider(); anchor("niulai-decision"); st.header("NIULAI最终判断")
    final_decision(
        f"NIULAI已经从早期热点爆发转入存量交易阶段。近7日仍有{len(posts)}条有效讨论，但价格{current_return:+.1%}，"
        "发帖峰值也存在少量账号集中放大的情况，因此暂未看到新一轮自然扩散带动价格反转的证据。"
        "它更适合用于观察成熟Meme的持仓情绪和平台预期，而不是作为早期发现信号；持仓结构、权限和退出成本仍需独立核验。"
    )

    st.divider(); anchor("niulai-benchmark"); st.header("指标校准与对照")
    ax1 = read_json(X_HEAT)["social_attention"]
    history_author_counts = history_posts.author_id.value_counts()
    benchmark = [
        ["AX1", f"{ax1['unique_posts']:,}", f"{ax1['unique_authors']:,}", f"{ax1['top_10_author_post_share']:.1%}", f"{ax1['original_share']:.1%}", AX1_SAMPLE_SCOPE],
        ["NIULAI", f"{len(history_posts):,}", f"{history_posts.author_id.nunique():,}", f"{history_author_counts.head(10).sum()/len(history_posts):.1%}", f"{history_posts.post_type.eq('original').mean():.1%}", NIULAI_HISTORY_SCOPE],
        ["TRUMP", "—", "—", "—", "—", "待同口径采集"],
    ]
    st.dataframe(pd.DataFrame(benchmark, columns=["代币", "帖子", "作者", "Top10作者占比", "原创占比", "样本范围"]), width="stretch", hide_index=True)
    st.info("校准表用于检查作者集中度与原创结构；由于币龄和采集窗口不同，不用帖子总量直接判断谁更热门。")

    st.divider(); anchor("niulai-evidence"); st.header("原始证据与分析口径")
    st.markdown(f"- X历史样本：{NIULAI_HISTORY_SCOPE}，实体消歧后{len(history_posts)}条。\n- X当前判断：{NIULAI_CURRENT_SCOPE}，共{len(posts)}条。\n- 历史补充：AP解释电影走红；Odaily/PANews重建Web2→链上阶段；Binance公告确认合约时间。\n- 市场：GeckoTerminal主池96根日线 + 168小时OHLCV。\n- 限制：8–10月按时间窗封顶，不是全量帖子，不能拿月度条数直接比较热度。")
    with st.expander("查看历史事件与原始帖子"):
        st.dataframe(selected[["event_time_utc", "event_type", "source_account", "raw_text", "source_url"]].sort_values("event_time_utc"), width="stretch", hide_index=True)
        st.dataframe(history_posts.sort_values("created_at_utc", ascending=False)[["created_at_utc", "entity_match", "post_type", "text", "lang", "total_interactions", "source_url"]].head(500), width="stretch", hide_index=True, column_config={"source_url": st.column_config.LinkColumn("原帖", display_text="打开")})


def render_dashboard() -> None:
    st.set_page_config(page_title="Meme社媒信号分析工具", page_icon="🔎", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.title("Meme Signal Lab")
    st.markdown(
        """
        <section class="product-hero">
          <div class="hero-kicker"><span class="live-dot"></span>Social intelligence workspace</div>
          <div class="hero-title-row">
            <h1>Meme Signal Lab</h1>
            <span class="hero-badge">RESEARCH MODE</span>
          </div>
          <p class="hero-copy">把分散的社媒讨论、市场变化和风险证据，整理成一条可核验的 Meme 研究路径。</p>
          <div class="hero-meta">
            <span>X API · 有界采集</span>
            <span>Go + Python</span>
            <span>市场与社媒对齐</span>
            <span>不构成投资建议</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_ca_workspace()
    st.divider()
    st.subheader("社媒分析案例")
    token = st.radio("选择案例", ["AX1", "NIULAI"], horizontal=True)
    st.divider()
    nav_col, case_col = st.columns([1.05, 4.95], gap="large")
    with nav_col:
        case_navigation(token)
    with case_col:
        render_ax1() if token == "AX1" else render_niulai(load_events(EVENTS))
    st.divider(); st.caption("公开数据研究原型 · 不构成投资建议")
