# Meme Signal Lab

**Meme 社媒信号分析工具** · [Live demo](https://meme-signal-lab.streamlit.app/)

Meme Signal Lab is a reproducible research prototype that connects public social discussion, market activity and risk evidence. It helps answer **why a token is being noticed, who is spreading it, what kind of attention it is receiving, and which claims remain unverified**.

The product does not predict the next winning token. It turns noisy evidence into a time-ordered research path.

## What it answers

Most token dashboards show price, volume and social posts as separate widgets. This project connects them into five questions:

1. Why is this token being discussed now?
2. Is attention driven by original discussion, product explanation, campaign activity or repeated promotion?
3. Which participant groups are visible in the public conversation?
4. Does social activity lead, coincide with or diverge from price and volume?
5. Which contract, holder and execution risks remain unverified?

The interface separates **observed facts**, **rule-based classifications** and **missing evidence**. A high post count is never presented as a buy signal.

## Live cases

| Case | Research window | Main finding |
| --- | --- | --- |
| **AX1** | Launch-period X and hourly market data | Discussion and market activity expanded together, but campaign content and incomplete on-chain evidence prevent a simple “organic heat” conclusion. |
| **NIULAI** | Historical windows plus a continuous recent window | Web2 attention, ticker translation, social proof and exchange access formed distinct stages; current holder discussion is not equivalent to the initial breakout. |

The public demo contains fixed, reproducible research snapshots. Live X API collection is not exposed to visitors.

## System design

```text
X API / market APIs / timestamped manual evidence
                        │
                        ▼
        Go collectors: pagination, retry, result caps
                        │
                        ▼
   Raw JSON → Python/Pandas validation and entity resolution
                        │
                        ▼
 Topic / stance / speech-act features + temporal market joins
                        │
                        ▼
           Streamlit evidence and decision dashboard
```

### Engineering decisions

- **Bounded collection:** every X query has an explicit time window and result cap.
- **Entity resolution:** contract address, chain, ticker and context prevent same-name tokens from contaminating a case.
- **Event time first:** timestamps are stored in UTC and converted only for display.
- **Reproducible metrics:** aggregates can be rebuilt from committed processed snapshots.
- **Evidence states:** verified, secondary, inferred and missing evidence remain distinguishable.
- **Request safety:** live collection is administrator-only and capped by result count; secrets and raw API responses are excluded from Git.

## Repository map

```text
app.py                 Streamlit entry point
dashboard.py           Product UI and visual analysis
collector/             Go X API collectors and tests
pipeline/              Python validation and feature pipelines
data/manual/           Timestamped manually verified evidence
data/processed/        Reproducible public research snapshots
scripts/               Collection, build and release checks
tests/                 Python pipeline tests
docs/                  Architecture, methodology and data contracts
```

## Run locally

Requirements: Python 3.11–3.14 and Go 1.22+.

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./scripts/start_app.sh
```

Open <http://localhost:8501>.

Run the verification suite:

```bash
./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/python -m pytest -q
cd collector && go test ./...
```

## Data quality and limitations

- X data comes from official API queries with preserved query windows and de-duplication keys; it is not described as a complete copy of the platform.
- Market and social series are aligned for temporal comparison, not causal attribution.
- Public-account classifications are research labels, not verified identities or wallet ownership.
- Dynamic holder, contract and liquidity fields must be rechecked before use.
- Kafka/Flink appears only as a documented scale-out design, not as a deployed production claim.

More detail: [case study](docs/portfolio_case_study.md), [data dictionary](docs/data_dictionary.md), [source reliability](docs/data_source_status.md), [real-time architecture](docs/realtime_architecture.md), and [deployment](docs/deployment.md).

## Privacy and release controls

- `.env`, Streamlit secrets, raw API responses, virtual environments and caches are excluded from Git.
- The public application contains no personal contact information.
- Third-party data remains subject to its original provider's terms.
- This is a research prototype, not trading execution or investment advice.
