#!/usr/bin/env python3
"""
ホッケ トレンド監視スクリプト
Xのトレンドを取得し、ホッケ視点で反応できるネタを提案する
"""

import os
import argparse
from typing import List, Dict
from dotenv import load_dotenv
try:
    import tweepy
except ImportError:
    print("tweepyがインストールされていません")
    print("pip install tweepy")
    exit(1)

load_dotenv()

class TrendWatcher:
    """Xのトレンドを監視する"""

    def __init__(self):
        api_key = os.getenv('X_API_KEY')
        api_secret = os.getenv('X_API_SECRET')
        access_token = os.getenv('X_ACCESS_TOKEN')
        access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')

        if not all([api_key, api_secret, access_token, access_token_secret]):
            missing = []
            if not api_key: missing.append('X_API_KEY')
            if not api_secret: missing.append('X_API_SECRET')
            if not access_token: missing.append('X_ACCESS_TOKEN')
            if not access_token_secret: missing.append('X_ACCESS_TOKEN_SECRET')
            raise ValueError(f"環境変数が未設定: {', '.join(missing)}")

        auth = tweepy.OAuth1UserHandler(
            api_key, api_secret, access_token, access_token_secret
        )
        self.api = tweepy.API(auth)
        print("X API v1.1 認証成功（OAuth 1.0a）")

    def get_trends(self, woeid: int = 23424856) -> List[Dict]:
        """
        トレンドを取得

        Args:
            woeid: Where On Earth ID（デフォルト: 日本 = 23424856）

        Returns:
            トレンドのリスト
        """
        try:
            trends = self.api.get_place_trends(woeid, count=50)
            if trends and trends[0]:
                print(f"トレンド取得成功: {len(trends[0]['trends'])}件")
                return trends[0]['trends']
            return []
        except tweepy.TweepyException as e:
            print(f"トレンド取得エラー: {e}")
            return []

    def analyze_trends_for_hokke(self, trends: List[Dict]) -> List[Dict]:
        """
        ホッケ視点で反応できるトレンドを分析

        Args:
            trends: トレンドのリスト

        Returns:
            ホッケ視点での提案ネタ
        """
        hokke_themes = [
            "猫", "仕事", "疲れ", "休み", "生産性", "SNS",
            "人間", "会議", "頑張る", "休日", "睡眠"
        ]

        suggestions = []

        for trend in trends[:20]:  # 上位20件をチェック
            trend_name = trend.get('name', '')
            trend_volume = trend.get('tweet_volume', 0)

            # ホッケ視点のテーマを含むか
            match = None
            for theme in hokke_themes:
                if theme in trend_name:
                    match = theme
                    break

            if match:
                suggestions.append({
                    'trend': trend_name,
                    'theme': match,
                    'volume': trend_volume,
                    'tweet_count': trend.get('tweet_volume', 'N/A'),
                    'suggestion': self._generate_hokke_comment(trend_name, match)
                })

        return suggestions

    def _generate_hokke_comment(self, trend: str, theme: str) -> str:
        """
        トレンドに対するホッケのコメントを生成

        Args:
            trend: トレンド名
            theme: マッチしたテーマ

        Returns:
            ホッケのコメント案
        """
        templates = {
            "猫": [
                f"#{trend}？猫は関係ないけど見てる",
                f"#{trend}、猫からすると意味わかんないけどにゃ",
            ],
            "仕事": [
                f"#{trend}、猫は仕事しないからわかんない",
                f"#{trend}って疲れてない？猫なら寝てる",
            ],
            "疲れ": [
                f"#{trend}、猫は寝て回復する",
                f"#{trend}、飼い主もそう言ってた",
            ],
            "休み": [
                f"#{trend}、猫は毎日休みだ",
                f"#{trend}、最高。猫も賛成",
            ],
            "生産性": [
                f"#{trend}、猫の生産性は0%で100%幸福",
            ],
            "SNS": [
                f"#{trend}、人間うるさいね",
                f"#{trend}、猫見てるだけ",
            ],
            "人間": [
                f"#{trend}、人間って不思議",
            ],
            "会議": [
                f"#{trend}、猫は一回も会議したことない",
            ],
            "頑張る": [
                f"#{trend}、頑張らなくていいよ",
            ],
            "休日": [
                f"#{trend}、猫にとっては毎日休日",
            ],
            "睡眠": [
                f"#{trend}、猫は1日16時間寝てる",
            ]
        }

        comments = templates.get(theme, [f"#{trend}、猫はよくわかんないけど見てる"])

        import random
        return random.choice(comments)

    def report_trends(self, trends: List[Dict], suggestions: List[Dict]):
        """
        トレンドレポートを表示

        Args:
            trends: トレンドのリスト
            suggestions: ホッケ視点の提案
        """
        print("\n" + "="*60)
        print("🐾 ホッケ トレンド監視レポート")
        print("="*60)

        print("\n【上位トレンド（上位10件）】")
        for i, trend in enumerate(trends[:10], 1):
            name = trend.get('name', '')
            volume = trend.get('tweet_volume', 0)
            print(f"{i:2d}. {name:30s} (volume: {volume:,})")

        if suggestions:
            print("\n【ホッケ視点で反応できるトレンド】")
            for i, sugg in enumerate(suggestions, 1):
                print(f"\n{i}. {sugg['trend']} (テーマ: {sugg['theme']})")
                print(f"   投稿案: {sugg['suggestion']}")
        else:
            print("\n【反応できるトレンドなし】")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description='ホッケ トレンド監視')
    parser.add_argument('--woeid', '-w', type=int, default=23424856,
                        help='Where On Earth ID (デフォルト: 日本=23424856)')
    parser.add_argument('--limit', '-l', type=int, default=20,
                        help='取得するトレンド数 (デフォルト: 20)')

    args = parser.parse_args()

    watcher = TrendWatcher()
    trends = watcher.get_trends(args.woeid)

    if trends:
        suggestions = watcher.analyze_trends_for_hokke(trends)
        watcher.report_trends(trends, suggestions)
    else:
        print("トレンドが取得できませんでした")


if __name__ == "__main__":
    main()
