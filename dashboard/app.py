"""ホッケ運用ダッシュボード - FastAPI アプリケーション"""

import copy
import logging
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from data_loader import load_all_dashboard_data

logger = logging.getLogger(__name__)

app = FastAPI(title="ホッケダッシュボード")

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path(__file__).parent / "templates"

STATIC_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

DASHBOARD_TEMPLATE = TEMPLATE_DIR / "dashboard.html"

_EMPTY_DATA: dict = {
    "auto_post_state": {"date": "不明", "target_today": 0, "consecutive_skips": 0},
    "last_post_time": None,
    "recent_posts": [],
    "category_stats": [],
    "strategy": {"preferred_categories": [], "avoid_categories": [], "guidance": "データなし"},
    "reply_strategy": {"preferred_categories": [], "avoid_categories": [], "guidance": "データなし"},
    "reply_summary": {"total": 0, "posted": 0, "posted_rate": 0, "recent": []},
    "log_errors": [],
}


def _load_data_safe() -> dict:
    """データを読み込み、予期しない例外時は空データを返す。"""
    try:
        result = load_all_dashboard_data()
    except Exception:
        logger.exception("ダッシュボードデータの読み込みに失敗しました")
        return copy.deepcopy(_EMPTY_DATA)
    if not isinstance(result, dict):
        logger.error("load_all_dashboard_data が dict 以外を返しました: %s", type(result))
        return copy.deepcopy(_EMPTY_DATA)
    return result


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not DASHBOARD_TEMPLATE.exists():
        return PlainTextResponse(
            "ダッシュボードは準備中です。/api/data でデータを確認できます。",
            status_code=200,
        )
    data = _load_data_safe()
    data["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return templates.TemplateResponse("dashboard.html", {"request": request, **data})


@app.get("/api/data")
def api_data():
    data = _load_data_safe()
    data["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return data
