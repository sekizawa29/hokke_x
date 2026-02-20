#!/usr/bin/env python3
"""
ホッケ Scheduled Post Executor
予約投稿をチェックし、時刻が来たら実行する
GitHub Actionsから定期実行される
"""

import json
import sys
import random
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

QUEUE_FILE = SCRIPT_DIR / "post_queue.json"
TEMPLATES_DIR = SCRIPT_DIR / "post_templates"
CHECK_ENGAGEMENT = SCRIPT_DIR / "check_engagement.py"
X_POSTER = SCRIPT_DIR / "x_poster.py"

TEMPLATE_TO_HOOK = {
    "relaxation": "脱力系",
    "cat_photo": "猫写真",
    "sharp": "鋭い一言",
    "daily_observation": "日常観察",
    "news": "時事ネタ",
    "useful": "たまに有益",
}
HOOK_TO_TEMPLATE = {v: k for k, v in TEMPLATE_TO_HOOK.items()}


def load_queue() -> Tuple[List[Dict[str, Any]], bool]:
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get("scheduled_posts", []), True
            if isinstance(data, list):
                return data, False
    return [], False


def save_queue(queue: List[Dict[str, Any]], wrapped: bool) -> None:
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        if wrapped:
            json.dump({"scheduled_posts": queue}, f, ensure_ascii=False, indent=2)
        else:
            json.dump(queue, f, ensure_ascii=False, indent=2)


def get_due_posts(queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """投稿時刻を過ぎたpending投稿を抽出"""
    now = datetime.utcnow() + timedelta(hours=9)  # JST
    due = []
    for post in queue:
        if post.get('status') != 'pending':
            continue
        try:
            scheduled = datetime.strptime(post['scheduled_at'], "%Y-%m-%d %H:%M")
            if scheduled <= now:
                due.append(post)
        except (ValueError, KeyError) as e:
            print(f"日時パースエラー: {post.get('id', '?')} - {e}")
    return due


def load_templates() -> List[Dict[str, Any]]:
    templates: List[Dict[str, Any]] = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    templates.append(data)
        except (OSError, json.JSONDecodeError) as e:
            print(f"テンプレート読み込み失敗: {path.name} - {e}")
    return templates


def get_recommended_hook_categories() -> List[str]:
    if not CHECK_ENGAGEMENT.exists():
        print("check_engagement.py が見つからないため推薦カテゴリをスキップ")
        return []

    cmd = [sys.executable, str(CHECK_ENGAGEMENT), "--recommend"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            check=False
        )
    except OSError as e:
        print(f"推薦カテゴリ取得エラー: {e}")
        return []

    output = f"{result.stdout}\n{result.stderr}"
    if result.returncode != 0:
        print("check_engagement.py --recommend の実行に失敗")
        print(output.strip())
        return []

    priorities: List[str] = []
    candidates: List[str] = []
    unknowns: List[str] = []
    for line in output.splitlines():
        m = re.match(r"^(優先|候補|未知):\s*([^\[\(]+)", line.strip())
        if not m:
            continue
        level = m.group(1)
        cat = m.group(2).strip()
        if level == "優先":
            priorities.append(cat)
        elif level == "候補":
            candidates.append(cat)
        else:
            unknowns.append(cat)

    ordered = priorities + candidates + unknowns
    if ordered:
        print(f"推薦カテゴリ順: {', '.join(ordered)}")
    else:
        print("推薦カテゴリが解析できなかったためテンプレートを通常選択")
    return ordered


def choose_template(templates: List[Dict[str, Any]], recommended_hooks: List[str]) -> Optional[Dict[str, Any]]:
    if not templates:
        return None

    by_category: Dict[str, List[Dict[str, Any]]] = {}
    for t in templates:
        cat = t.get("category", "")
        by_category.setdefault(cat, []).append(t)

    for hook_cat in recommended_hooks:
        template_cat = HOOK_TO_TEMPLATE.get(hook_cat)
        if template_cat and by_category.get(template_cat):
            return random.choice(by_category[template_cat])

    return random.choice(templates)


def maybe_fill_post_from_template(post: Dict[str, Any], templates: List[Dict[str, Any]], recommended_hooks: List[str]) -> Dict[str, Any]:
    # textが空、またはテンプレート利用フラグがある場合はカテゴリ推薦に基づいて補完
    use_template = post.get("use_template") or post.get("from_template") or not post.get("text")
    if not use_template:
        return post

    selected = choose_template(templates, recommended_hooks)
    if not selected:
        print("テンプレートが見つからないため、既存投稿データを使用")
        return post

    template_cat = selected.get("category", "")
    hook_cat = TEMPLATE_TO_HOOK.get(template_cat, "未分類")
    post["text"] = selected.get("template", post.get("text", ""))
    post["hook_category"] = hook_cat
    post["selected_template"] = selected.get("name", "")
    print(f"テンプレート選択: {selected.get('name', 'unknown')} / {hook_cat}")
    return post


def run_x_poster(post: Dict[str, Any]) -> bool:
    cmd = [sys.executable, str(X_POSTER)]
    thread_file: Optional[str] = None

    hook_category = post.get("hook_category") or post.get("hookCategory") or "未分類"
    thread_data = post.get("thread")
    if thread_data:
        normalized_thread = []
        for tweet in thread_data:
            item = dict(tweet)
            if item.get("image"):
                item["image"] = str(SCRIPT_DIR.parent / item["image"])
            normalized_thread.append(item)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(normalized_thread, tmp, ensure_ascii=False)
            thread_file = tmp.name
        cmd += ["--thread", thread_file]
    else:
        text = post.get("text", "")
        cmd += ["--text", text, "--hook-category", hook_category]

        if post.get("image"):
            image_path = str(SCRIPT_DIR.parent / post["image"])
            cmd += ["--image", image_path]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            check=False
        )
    except OSError as e:
        print(f"x_poster.py 実行エラー: {e}")
        return False
    finally:
        if thread_file:
            try:
                Path(thread_file).unlink(missing_ok=True)
            except OSError:
                pass

    output = f"{result.stdout}\n{result.stderr}".strip()
    if output:
        print(output)

    if result.returncode != 0:
        return False

    # x_poster.py は失敗時も終了コード0の可能性があるため出力を確認
    return ("投稿成功:" in output) or ("画像付き投稿成功:" in output) or ("リプライ投稿成功:" in output)


def execute_post(post: Dict[str, Any], templates: List[Dict[str, Any]], recommended_hooks: List[str]) -> bool:
    post_id = post.get('id', '?')
    print(f"\n投稿実行: {post_id} (予約: {post.get('scheduled_at')})")

    try:
        post_to_run = maybe_fill_post_from_template(dict(post), templates, recommended_hooks)
        return run_x_poster(post_to_run)
    except Exception as e:
        print(f"投稿エラー: {e}")
        return False


def main():
    print(f"ホッケ Scheduler - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    queue, wrapped = load_queue()
    print(f"キュー: {len(queue)}件")

    if not queue:
        print("予約なし")
        return

    due_posts = get_due_posts(queue)
    print(f"投稿対象: {len(due_posts)}件")

    if not due_posts:
        print("現在投稿すべき予約なし")
        return

    templates = load_templates()
    recommended_hooks = get_recommended_hook_categories()

    success = 0
    for post in due_posts:
        ok = execute_post(post, templates, recommended_hooks)
        for p in queue:
            if p.get('id') == post.get('id'):
                p['status'] = 'completed' if ok else 'failed'
                p['executed_at'] = datetime.now().isoformat()
                break
        if ok:
            success += 1

    # 完了・失敗を除去して保存
    queue = [p for p in queue if p.get('status') == 'pending']
    save_queue(queue, wrapped)

    print(f"\n結果: {success}/{len(due_posts)}件成功, 残りキュー: {len(queue)}件")


if __name__ == "__main__":
    main()
