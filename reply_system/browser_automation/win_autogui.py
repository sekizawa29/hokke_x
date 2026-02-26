#!/usr/bin/env python3
"""
Windows側で実行する1件分のブラウザリプライ自動操作スクリプト。

python.exe win_autogui.py --url "https://x.com/user/status/123" --text "リプライ本文" [--dry-run]

終了コード: 0=成功, 1=ページ読み込み失敗, 2=リプライ欄不明, 3=投稿失敗
"""

import argparse
import glob
import io
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

# Windows Python の stdout/stderr を UTF-8 に強制
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).parent
IMG_DIR = SCRIPT_DIR / "img"
REPLY_IMG = IMG_DIR / "reply_placeholder.png"

# Chrome実行パスの候補
CHROME_PATHS = [
    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]

try:
    import pyautogui
    import pyperclip
except ImportError:
    print("ERROR: pyautogui / pyperclip が未インストールです", file=sys.stderr)
    print("  python.exe -m pip install pyautogui pyperclip", file=sys.stderr)
    sys.exit(1)

# 緊急停止: マウスを画面左上に移動で停止
pyautogui.FAILSAFE = True
# デフォルトの待機時間
pyautogui.PAUSE = 0.3

# URLバリデーション: x.com のツイートURLのみ許可
URL_PATTERN = re.compile(r"^https://x\.com/[A-Za-z0-9_]+/status/\d+$")

# キャプチャ一時ファイルの上限（これ以上あれば古い順に削除）
MAX_TEMP_SCREENSHOTS = 3


def validate_url(url: str) -> bool:
    """URLがx.comのツイートURLであることを検証"""
    return bool(URL_PATTERN.match(url))


def find_chrome() -> str | None:
    """Chrome実行ファイルのパスを探す"""
    for path in CHROME_PATHS:
        if os.path.isfile(path):
            return path
    return None


def verify_chrome_active() -> bool:
    """Chromeプロセスが最前面にあることを確認する。

    PowerShell自身がフォーカスを奪う問題を回避するため、
    起動前にフォアグラウンドウィンドウのハンドルを記録してから
    そのプロセス名を取得する方式ではなく、
    Chromeウィンドウが存在しフォアグラウンドであるかを確認する。
    """
    # CreateNoWindow フラグ付きで PowerShell を起動し、フォーカスを奪わない
    ps_cmd = (
        '$chrome = Get-Process chrome -ErrorAction SilentlyContinue '
        '| Where-Object { $_.MainWindowHandle -ne 0 }; '
        'if ($chrome) { "chrome_found" } else { "not_found" }'
    )
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            startupinfo=si,
        )
        output = result.stdout.strip().lower()
        if "chrome_found" in output:
            return True
        print("  ERROR: Chromeウィンドウが見つかりません")
        return False
    except Exception as e:
        print(f"  WARNING: Chrome検証スキップ: {e}")
        return True  # 検証不能時は続行（FAILSAFEで保護）


def activate_chrome():
    """PowerShell経由でChromeウィンドウを最前面にする"""
    ps_cmd = (
        'Add-Type -AssemblyName Microsoft.VisualBasic; '
        '[Microsoft.VisualBasic.Interaction]::AppActivate("Chrome")'
    )
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            timeout=5,
            startupinfo=si,
        )
        time.sleep(0.5)
        print("  Chrome をアクティブ化")
    except Exception as e:
        print(f"  Chrome アクティブ化失敗（続行）: {e}")


def open_tweet_page(url: str, wait_min: float = 4.0, wait_max: float = 6.0) -> bool:
    """Chromeを前面に出し、新タブでツイートページを開く（マウス不使用）。"""
    chrome_path = find_chrome()
    if chrome_path:
        try:
            subprocess.Popen(
                [chrome_path, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"ERROR: Chrome起動失敗: {e}", file=sys.stderr)
            return False
    else:
        import webbrowser
        print("  WARNING: Chromeパスが見つかりません。デフォルトブラウザで開きます")
        webbrowser.open(url)

    wait = random.uniform(wait_min, wait_max)
    print(f"  ページ読み込み待機: {wait:.1f}秒")
    time.sleep(wait)

    activate_chrome()

    if not verify_chrome_active():
        return False

    return True


# --- スクリーンショット管理 ---

def cleanup_temp_screenshots():
    """img/ 内の一時スクリーンショット（capture_*.png）を古い順に削除し上限を維持"""
    pattern = str(IMG_DIR / "capture_*.png")
    files = sorted(glob.glob(pattern), key=os.path.getmtime)
    while len(files) > MAX_TEMP_SCREENSHOTS:
        old = files.pop(0)
        os.remove(old)
        print(f"  古いキャプチャ削除: {Path(old).name}")


def capture_reference():
    """参照画像キャプチャモード。

    1. 全画面スクショを撮影して一時保存
    2. ユーザーが手動で「返信をポスト」部分をトリミング
    3. reply_placeholder.png として保存
    """
    IMG_DIR.mkdir(exist_ok=True)

    print("=== 参照画像キャプチャ ===")
    print("X.comのツイート詳細ページを表示した状態で実行してください")
    print("5秒後にスクリーンショットを撮影します...\n")
    time.sleep(5)

    # 全画面スクショ撮影
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    temp_file = IMG_DIR / f"capture_{timestamp}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(str(temp_file))
    print(f"  スクリーンショット保存: {temp_file}")

    # 古いキャプチャを自動削除
    cleanup_temp_screenshots()

    print()
    print("次の手順:")
    print(f"  1. {temp_file} を画像エディタで開く")
    print("  2. 「返信をポスト」のテキスト部分だけをトリミング")
    print(f"  3. {REPLY_IMG} として保存")
    print()
    print("  トリミング範囲の目安: プレースホルダーテキスト「返信をポスト」を")
    print("  含む横長の小さな領域（高さ20-30px程度）")


# --- リプライ欄フォーカス（画像認識） ---

def focus_reply_area(confidence: float = 0.8, retries: int = 3) -> bool:
    """画像認識で「返信をポスト」欄を見つけてクリックする。

    pyautogui.locateOnScreen で参照画像を画面上から検索し、
    見つかった位置をクリックしてフォーカスを当てる。
    """
    if not verify_chrome_active():
        print("  ERROR: Chrome が非アクティブ")
        return False

    if not REPLY_IMG.exists():
        print(f"  ERROR: 参照画像がありません: {REPLY_IMG}", file=sys.stderr)
        print("  --capture で参照画像を作成してください", file=sys.stderr)
        return False

    for attempt in range(1, retries + 1):
        print(f"  リプライ欄を画像認識で検索中... (試行 {attempt}/{retries})")
        try:
            location = pyautogui.locateOnScreen(
                str(REPLY_IMG),
                confidence=confidence,
            )
        except Exception as e:
            print(f"  画像認識エラー: {e}")
            if "opencv" in str(e).lower() or "cv2" in str(e).lower():
                print("  ※ opencv-python が必要です: python.exe -m pip install opencv-python")
            return False

        if location:
            center = pyautogui.center(location)
            print(f"  リプライ欄発見: ({center.x}, {center.y})")
            pyautogui.click(center.x, center.y, duration=random.uniform(0.2, 0.5))
            time.sleep(0.5)

            if not verify_chrome_active():
                print("  ERROR: クリック後にChromeが非アクティブ")
                return False

            print("  リプライ欄にフォーカス完了")
            return True

        # リトライ前にスクロールして再検索
        if attempt < retries:
            print("  見つからず - 少しスクロールして再試行")
            pyautogui.scroll(-3)
            time.sleep(1.0)

    print("  ERROR: リプライ欄が見つかりませんでした")
    return False


def paste_text(text: str) -> bool:
    """クリップボード経由でテキストを貼り付ける"""
    try:
        pyperclip.copy(text)
    except Exception as e:
        print(f"ERROR: クリップボードコピー失敗: {e}", file=sys.stderr)
        return False

    time.sleep(0.2)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.5)

    print(f"  テキスト貼り付け完了: {text[:50]}...")
    return True


def submit_post() -> bool:
    """Ctrl+Enter で投稿する"""
    if not verify_chrome_active():
        print("  ERROR: 投稿中止 - Chromeが非アクティブ")
        return False

    print("  投稿実行: Ctrl+Enter")
    pyautogui.hotkey("ctrl", "Return")
    time.sleep(2.0)
    return True


def close_tab():
    """現在のタブを閉じる"""
    pyautogui.hotkey("ctrl", "w")
    time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description="1件分のブラウザリプライ自動操作")
    parser.add_argument("--url", default=None, help="ツイートURL")
    parser.add_argument("--text", default=None, help="リプライ本文")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず貼り付けまで")
    parser.add_argument("--capture", action="store_true",
                        help="参照画像キャプチャモード")
    parser.add_argument("--confidence", type=float, default=0.8,
                        help="画像認識の一致度 (0.0-1.0, default: 0.8)")
    parser.add_argument("--page-load-min", type=float, default=4.0)
    parser.add_argument("--page-load-max", type=float, default=6.0)
    args = parser.parse_args()

    if args.capture:
        capture_reference()
        return

    if not args.url or not args.text:
        parser.error("--url と --text は必須です（--capture 以外）")

    # URL バリデーション
    if not validate_url(args.url):
        print(f"ERROR: 無効なURL形式です: {args.url}", file=sys.stderr)
        print("  x.com のツイートURL (https://x.com/user/status/ID) のみ対応", file=sys.stderr)
        sys.exit(1)

    # 待機時間バリデーション
    wait_min = max(0.0, args.page_load_min)
    wait_max = max(wait_min, args.page_load_max)

    print(f"=== win_autogui: {'DRY-RUN' if args.dry_run else 'LIVE'} ===")
    print(f"  URL: {args.url}")
    print(f"  Text: {args.text[:60]}...")

    # Step 1: ページを開く
    if not open_tweet_page(args.url, wait_min, wait_max):
        sys.exit(1)

    # Step 2: リプライ欄にフォーカス（画像認識）
    if not focus_reply_area(confidence=args.confidence):
        close_tab()
        sys.exit(2)

    # Step 3: テキスト貼り付け
    if not paste_text(args.text):
        close_tab()
        sys.exit(3)

    # Step 4: 投稿 (dry-run時はスキップ)
    if args.dry_run:
        print("  [DRY-RUN] 投稿スキップ - 3秒後にタブを閉じます")
        time.sleep(3.0)
    else:
        if not submit_post():
            close_tab()
            sys.exit(3)
        print("  投稿完了")

    # Step 5: タブを閉じる
    close_tab()
    print("  完了")


if __name__ == "__main__":
    main()
