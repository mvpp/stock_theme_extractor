# Stock Themes — Deployment Guide

## Context

This guide covers deploying the `stock_themes` system end-to-end: from a fresh machine to a fully populated SQLite database of thematic labels for all US-listed stocks, with ongoing daily social collection and monthly theme refresh.

---

## 0. Bug Fix — `pyproject.toml` build backend (MUST DO FIRST)

The current `pyproject.toml` has an incorrect build backend that causes:
```
pip._vendor.pyproject_hooks._impl.BackendUnavailable: Cannot import 'setuptools.backends._legacy'
```

**File:** `pyproject.toml`

**Change:** Replace line 22:
```toml
# BEFORE (broken):
build-backend = "setuptools.backends._legacy:_Backend"

# AFTER (correct):
build-backend = "setuptools.build_meta"
```

The `setuptools.backends._legacy:_Backend` is an internal pip fallback that was never meant to be used in `pyproject.toml`. The standard backend is `setuptools.build_meta`.

---

## 1. Prerequisites

| Requirement | Detail |
|---|---|
| **Python** | 3.11 or newer |
| **OS** | macOS, Linux, or WSL2. Windows native works but cron requires Task Scheduler. |
| **RAM** | 4 GB minimum, 8 GB+ recommended for batch processing |
| **Disk** | ~2 GB free (embedding model ~90 MB, DB ~200 MB at scale, cache ~500 MB) |
| **Internet** | Required for all API calls; no offline mode |

### API Keys

| Key | Where to get it | Required? | Cost |
|---|---|---|---|
| `MOONSHOT_API_KEY` | [platform.moonshot.ai](https://platform.moonshot.ai) → Console → API Keys. Recharge at least $1 to activate. | Yes (for LLM extraction) | ~$5 for all stocks >$1B market cap |
| `SEC_EDGAR_EMAIL` | Any valid email you control. SEC requires a User-Agent identity. | Yes (for SEC filings) | Free |

Without `MOONSHOT_API_KEY`, the system still works — it just skips LLM extraction and relies on the other 6 methods (embedding similarity, keyword NLP, patent mapping, news, SIC codes, social).

---

## 2. Installation

```bash
# Clone or navigate to the project
cd /Users/xihanliu/Programs/stock_themes

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # on macOS/Linux
# .venv\Scripts\activate   # on Windows

# Install the package in editable mode
pip install -e .

# (Optional) Install dev dependencies for testing/linting
pip install -e ".[dev]"
```

### What gets installed

| Package | Size | Purpose |
|---|---|---|
| `torch` | ~800 MB | PyTorch (CPU-only by default) |
| `sentence-transformers` | ~50 MB | Embedding model framework |
| `edgartools` | ~10 MB | SEC EDGAR filing parser |
| `yfinance` | ~5 MB | Yahoo Finance client |
| `openai` | ~5 MB | Moonshot API client (OpenAI-compatible) |
| Others | ~10 MB | requests, tqdm, python-dotenv |

**Tip — CPU-only PyTorch (saves ~1.5 GB):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e .
```

---

## 3. Configuration

```bash
# Create your .env file from the template
cp .env.example .env
```

Edit `.env`:
```env
MOONSHOT_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
SEC_EDGAR_EMAIL=yourname@yourdomain.com
```

### All tunable settings (`stock_themes/config.py`)

| Setting | Default | What it controls |
|---|---|---|
| `LLM_MARKET_CAP_THRESHOLD` | `1e9` ($1B) | Stocks above this get LLM extraction |
| `LLM_MODEL` | `kimi-k2-5` | Moonshot model identifier |
| `LLM_BASE_URL` | `https://api.moonshot.ai/v1` | API endpoint |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | HuggingFace sentence-transformer model |
| `SIMILARITY_THRESHOLD` | `0.6` | Cosine similarity cutoff for chunk pre-filtering |
| `CHUNK_SIZE_WORDS` | `200` | Words per text chunk |
| `BATCH_SIZE` | `50` | Tickers per processing batch |
| `LLM_DELAY_SECONDS` | `0.5` | Pause between LLM API calls |
| `SEC_RATE_LIMIT_DELAY` | `0.15` | Pause between SEC API calls (~7 req/sec) |
| `YAHOO_RATE_LIMIT_DELAY` | `0.5` | Pause between Yahoo Finance calls |

---

## 4. First Run — Single Ticker Test

Before running the full batch, verify everything works with one ticker:

```python
from stock_themes import get_themes

result = get_themes("AAPL", use_llm=True)
print(f"Company: {result.company_name}")
print(f"Sources: {result.metadata.get('sources_used', [])}")
print(f"Themes:")
for t in result.themes:
    print(f"  {t.confidence:.0%}  {t.name:<30s}  [{t.canonical_category}]  via {t.source.value}")
```

**What happens on first call:**
1. `all-MiniLM-L6-v2` model downloads from HuggingFace (~90 MB, ~2 min)
2. Theme embeddings computed for 200+ themes and cached to `~/.cache/stock_themes/theme_embeddings.pt`
3. Yahoo Finance fetches company info (~1s)
4. SEC EDGAR fetches latest 10-Q (or fallback 10-K/S-1) (~3s)
5. PatentsView searches patents by assignee (~2s)
6. GDELT fetches news themes (~2s)
7. Text chunked, embedded, filtered (threshold > 0.6)
8. All 7 extractors run (SIC, keyword, patent, embedding, news, LLM)
9. Ensemble merges + ranks → `ThemeResult`

**Expected output for AAPL** (themes will vary based on current filings):
```
Company: Apple Inc.
Themes:
  95%  wearable technology              [consumer & lifestyle]  via llm
  92%  mobile                           [digital economy]       via embedding
  88%  artificial intelligence          [technology]            via llm
  85%  cloud computing                  [technology]            via keyword
  ...
```

**Total time:** ~15-30 seconds for first ticker (includes model download on very first run).

---

## 5. Full Database Build

```python
from stock_themes import build_database

build_database(
    db_path="stock_themes.db",
    llm_market_cap_threshold=1e9,   # LLM for stocks >$1B
    max_themes_per_stock=10,
    skip_existing=True,             # skip already-processed tickers
)
```

Or from the command line:
```bash
python -c "from stock_themes import build_database; build_database()"
```

### Time & cost estimates

| Stocks | LLM? | Estimated time | LLM cost |
|---|---|---|---|
| ~8,000 (all US) | No | ~6-12 hours | $0 |
| ~8,000 (all US) | Yes for >$1B (~4,000) | ~18-36 hours | ~$5 |
| Custom list of 100 | Yes | ~30-60 min | <$0.50 |

**Why so long?** Rate limits. SEC EDGAR: 7 req/sec. Yahoo Finance: 2 req/sec. Plus PatentsView and GDELT calls per ticker. The bottleneck is sequential API calls, not computation.

### Processing a custom ticker list

```python
from stock_themes.batch import run_batch

stats = run_batch(
    db_path="stock_themes.db",
    tickers=["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "JPM"],
)
print(stats)  # {"processed": 6, "skipped": 0, "failed": 0, "total": 6}
```

---

## 6. Querying the Database

Once populated, the database supports these queries:

```python
from stock_themes.db.queries import lookup, find_stocks, stats

# All themes for a stock
themes = lookup("AAPL")
for t in themes:
    print(f"  {t['confidence']:.0%} {t['name']} [{t['category']}] via {t['source']}")

# All stocks matching a theme
ai_stocks = find_stocks("artificial intelligence", min_confidence=0.5)
for s in ai_stocks:
    print(f"  {s['ticker']} {s['name']} ({s['confidence']:.0%})")

# Database statistics
print(stats())
# {"stocks": 8000, "themes": 180, "associations": 45000, "social_messages": 0}
```

### Direct SQL (for advanced queries)

```bash
sqlite3 stock_themes.db
```

```sql
-- Top 20 AI stocks
SELECT s.ticker, s.name, st.confidence
FROM stock_themes st
JOIN stocks s ON s.ticker = st.ticker
JOIN themes t ON t.id = st.theme_id
WHERE t.name = 'artificial intelligence'
ORDER BY st.confidence DESC LIMIT 20;

-- Theme distribution
SELECT t.name, COUNT(*) as stocks, ROUND(AVG(st.confidence),2) as avg_conf
FROM stock_themes st JOIN themes t ON t.id = st.theme_id
GROUP BY t.name ORDER BY stocks DESC LIMIT 30;

-- Stocks with 5+ themes
SELECT st.ticker, s.name, COUNT(*) as theme_count
FROM stock_themes st JOIN stocks s ON s.ticker = st.ticker
GROUP BY st.ticker HAVING theme_count >= 5
ORDER BY theme_count DESC;
```

---

## 7. Daily StockTwits Collection (Cron Job)

StockTwits only returns 30 messages per call. To get meaningful signal, collect daily and aggregate monthly.

### Manual run
```bash
# Collect for all tickers in the database
python -m stock_themes.data.social stock_themes.db

# Collect for specific tickers only
python -m stock_themes.data.social stock_themes.db AAPL TSLA NVDA
```

### Cron setup (Linux/macOS)

```bash
crontab -e
```

Add this line (runs daily at 6 PM UTC):
```cron
0 18 * * * cd /Users/xihanliu/Programs/stock_themes && /Users/xihanliu/Programs/stock_themes/.venv/bin/python -m stock_themes.data.social stock_themes.db >> /tmp/stock_themes_social.log 2>&1
```

### macOS launchd alternative

Create `~/Library/LaunchAgents/com.stock-themes.social.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stock-themes.social</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/xihanliu/Programs/stock_themes/.venv/bin/python</string>
        <string>-m</string>
        <string>stock_themes.data.social</string>
        <string>/Users/xihanliu/Programs/stock_themes/stock_themes.db</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/xihanliu/Programs/stock_themes</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/stock_themes_social.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/stock_themes_social.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.stock-themes.social.plist
```

After 30 days of daily collection, each ticker will have ~900 messages (30 per day minus bearish). This social signal gets used during the next monthly theme refresh.

---

## 8. Monthly Theme Refresh

Run `build_database()` again with `skip_existing=False` to reprocess all tickers with fresh data:

```python
from stock_themes import build_database

build_database(
    db_path="stock_themes.db",
    skip_existing=False,  # reprocess all tickers
)
```

Or create a monthly cron:
```cron
# First Saturday of each month at 2 AM
0 2 1-7 * 6 cd /Users/xihanliu/Programs/stock_themes && /Users/xihanliu/Programs/stock_themes/.venv/bin/python -c "from stock_themes import build_database; build_database(skip_existing=False)" >> /tmp/stock_themes_monthly.log 2>&1
```

This will:
1. Re-fetch company data from Yahoo Finance + SEC EDGAR (with cache)
2. Re-fetch patent data from PatentsView
3. Re-fetch news themes from GDELT (last 3 months)
4. Read accumulated StockTwits messages (past 30 days, neutral+positive only)
5. Re-run all 7 extractors with the fresh data
6. Overwrite old theme associations in the database

---

## 9. Docker Deployment (Optional)

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (saves 1.5 GB)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy and install project
COPY pyproject.toml .
COPY stock_themes/ stock_themes/
RUN pip install --no-cache-dir -e .

# Pre-download the embedding model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Volumes for persistent data
VOLUME ["/data", "/root/.cache/stock_themes"]

ENV MOONSHOT_API_KEY=""
ENV SEC_EDGAR_EMAIL="stock_themes@example.com"

CMD ["python", "-c", "from stock_themes import build_database; build_database(db_path='/data/stock_themes.db')"]
```

### docker-compose.yml

```yaml
version: "3.8"
services:
  stock-themes:
    build: .
    environment:
      - MOONSHOT_API_KEY=${MOONSHOT_API_KEY}
      - SEC_EDGAR_EMAIL=${SEC_EDGAR_EMAIL}
    volumes:
      - ./data:/data
      - cache:/root/.cache/stock_themes
    command: >
      python -c "from stock_themes import build_database; build_database(db_path='/data/stock_themes.db')"

  social-collector:
    build: .
    environment:
      - MOONSHOT_API_KEY=${MOONSHOT_API_KEY}
    volumes:
      - ./data:/data
      - cache:/root/.cache/stock_themes
    command: python -m stock_themes.data.social /data/stock_themes.db
    # Run daily via external scheduler (e.g., cron on host calling docker compose run)

volumes:
  cache:
```

### Build & run

```bash
docker compose build
docker compose run stock-themes          # full batch
docker compose run social-collector       # daily social collection
```

---

## 10. File & Directory Layout After Deployment

```
stock_themes/
├── .env                          # Your API keys (never commit)
├── .venv/                        # Virtual environment
├── stock_themes.db               # SQLite database (grows to ~200 MB)
├── pyproject.toml
├── stock_themes/                 # Source code
│   ├── __init__.py
│   ├── batch.py
│   ├── config.py
│   ├── models.py
│   ├── data/                     # 6 data providers
│   ├── extraction/               # 7 theme extractors
│   ├── semantic/                 # Chunker + embedder + filter
│   ├── taxonomy/                 # 200+ themes, SIC/CPC/GDELT mappings
│   └── db/                       # SQLite schema + store
│
~/.cache/stock_themes/            # Auto-created cache
├── theme_embeddings.pt           # Cached theme vectors (~1 MB)
├── yahoo_finance/                # Cached Yahoo responses
├── sec_edgar/                    # Cached SEC filing text
├── patentsview/                  # Cached patent data
└── gdelt/                        # Cached news data
```

---

## 11. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `BackendUnavailable: Cannot import 'setuptools.backends._legacy'` | Wrong build backend in `pyproject.toml` | Change `build-backend` to `"setuptools.build_meta"` (see Section 0) |
| `ModuleNotFoundError: torch` | PyTorch not installed | `pip install torch` |
| `ProviderError: SEC EDGAR...` | edgartools can't reach SEC | Check internet; SEC may be down; increase `SEC_RATE_LIMIT_DELAY` |
| `TickerNotFoundError` | Invalid or delisted ticker | Check ticker on Yahoo Finance; skip it |
| LLM returns empty themes | Moonshot API key invalid/empty | Verify `MOONSHOT_API_KEY` in `.env`; check balance at platform.moonshot.ai |
| `RuntimeError: All providers failed` | Both Yahoo + SEC failed for a ticker | Network issue or ticker not a US equity; logged and skipped in batch |
| Batch is slow | Rate limiting is working correctly | Expected: ~7 req/sec for SEC, ~2/sec for Yahoo. Full run takes 6-36 hours. |
| `torch.load` warning | PyTorch security change | Safe to ignore; we only load our own cached embeddings |
| StockTwits returns 0 messages | Ticker has no StockTwits activity | Normal for small/micro-cap stocks; other extractors still work |
| High memory usage | Embedding model + large text chunks | Close other apps; or set `CHUNK_SIZE_WORDS` smaller |
| DB locked | Multiple writers | SQLite WAL mode handles most cases. Don't run batch + social collector simultaneously on same DB file. |

---

## 12. Cost Summary per Monthly Cycle

| Item | Cost |
|---|---|
| Yahoo Finance API | $0 |
| SEC EDGAR API | $0 |
| PatentsView API | $0 |
| GDELT API | $0 |
| StockTwits API | $0 |
| Sentence-transformers (local CPU) | $0 |
| Kimi K2.5 LLM (~4,000 stocks >$1B, pre-filtered chunks) | ~$5 |
| **Total per month** | **~$5** |
