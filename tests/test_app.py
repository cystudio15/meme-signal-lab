from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).parents[1]


def test_streamlit_ax1_is_default_and_continuous():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()

    assert not app.exception
    assert [item.value for item in app.title] == ["Meme Signal Lab"]
    assert [item.label for item in app.text_input] == [
        "代币合约地址（CA）",
        "管理员口令",
    ]
    assert "生成近 7 日社媒观察" in [
        item.label for item in app.button
    ]
    assert not app.tabs
    headers = [item.value for item in app.header]
    for heading in [
        "AX1：现在发生什么？",
        "谁正在参与AX1讨论？",
        "社区话题、表达倾向与传播功能",
        "传播阶段与市场变化",
        "社媒与价格是否同步？",
        "交易前还要通过哪些风险闸门？",
        "AX1最终判断",
        "指标校准与对照",
        "原始证据与分析口径",
    ]:
        assert heading in headers
    metric_labels = [item.label for item in app.metric]
    for label in ["有效帖子", "独立作者", "活动动员内容", "Top 10", "区间成交"]:
        assert label in metric_labels


def test_streamlit_niulai_does_not_show_ax1_panels():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
    app.radio[0].set_value("NIULAI").run()

    assert not app.exception
    headers = [item.value for item in app.header]
    for heading in [
        "NIULAI：现在发生什么？",
        "谁正在参与NIULAI讨论？",
        "社区话题、表达倾向与传播功能",
        "完整发酵链路",
        "社媒与价格是否同步？",
        "交易前还要通过哪些风险闸门？",
        "NIULAI最终判断",
        "指标校准与对照",
        "原始证据与分析口径",
    ]:
        assert heading in headers
    assert "AX1：现在发生什么？" not in headers
    metric_labels = [item.label for item in app.metric]
    for label in ["历史有效样本", "历史独立作者", "近7日有效帖子", "近7日机器播报", "主池流动性"]:
        assert label in metric_labels


def test_ax1_phase_replay_is_in_continuous_story():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()

    assert "传播阶段与市场变化" in [item.value for item in app.header]
    assert not app.tabs
