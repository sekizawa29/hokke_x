#!/usr/bin/env python3
"""
Shared X API client.
All X API calls should go through this module so cost logging is never skipped.
"""

import os
from pathlib import Path
from typing import Optional, Any

import requests
import tweepy
from dotenv import load_dotenv

from cost_logger import log_api_usage

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"

load_dotenv(ENV_FILE)


class XApiClient:
    def __init__(self, require_user_auth: bool = False, require_bearer: bool = False):
        self.api_key = os.getenv("X_API_KEY")
        self.api_secret = os.getenv("X_API_SECRET")
        self.access_token = os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.bearer_token = os.getenv("X_BEARER_TOKEN")

        self.auth = None
        self.api_v1 = None
        self.client = None

        if require_user_auth:
            self._init_user_auth()
        if require_bearer and not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN が未設定")

    def _init_user_auth(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("X_API_KEY")
        if not self.api_secret:
            missing.append("X_API_SECRET")
        if not self.access_token:
            missing.append("X_ACCESS_TOKEN")
        if not self.access_token_secret:
            missing.append("X_ACCESS_TOKEN_SECRET")
        if missing:
            raise ValueError(f"環境変数が未設定: {', '.join(missing)}")

        self.auth = tweepy.OAuth1UserHandler(
            self.api_key, self.api_secret, self.access_token, self.access_token_secret
        )
        self.api_v1 = tweepy.API(self.auth)
        self.client = tweepy.Client(
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )

    # ---- user-auth endpoints ----
    def verify_credentials(self) -> Any:
        if not self.api_v1:
            self._init_user_auth()
        user = self.api_v1.verify_credentials()
        log_api_usage(
            "user_read",
            1,
            "GET /1.1/account/verify_credentials",
            context="x_api_client.verify_credentials",
            metadata={"screen_name": getattr(user, "screen_name", None)},
        )
        return user

    def media_upload(self, filename: str) -> Any:
        if not self.api_v1:
            self._init_user_auth()
        media = self.api_v1.media_upload(filename=filename)
        log_api_usage(
            "content_create",
            1,
            "POST media/upload",
            context="x_api_client.media_upload",
            metadata={"filename": filename},
        )
        return media

    def create_tweet(
        self,
        *,
        text: str,
        media_ids: Optional[list[int]] = None,
        in_reply_to_tweet_id: Optional[str] = None,
        context: str = "",
        metadata: Optional[dict] = None,
    ) -> Any:
        if not self.client:
            self._init_user_auth()

        kwargs: dict[str, Any] = {"text": text}
        if media_ids:
            kwargs["media_ids"] = media_ids
        if in_reply_to_tweet_id:
            kwargs["in_reply_to_tweet_id"] = in_reply_to_tweet_id

        response = self.client.create_tweet(**kwargs)

        endpoint = "POST /2/tweets"
        if in_reply_to_tweet_id:
            endpoint = "POST /2/tweets (reply)"
        elif media_ids:
            endpoint = "POST /2/tweets (with media)"

        event_meta = {"text_len": len(text)}
        if metadata:
            event_meta.update(metadata)
        if in_reply_to_tweet_id:
            event_meta["reply_to_tweet_id"] = str(in_reply_to_tweet_id)

        log_api_usage(
            "content_create",
            1,
            endpoint,
            context=context or "x_api_client.create_tweet",
            metadata=event_meta,
        )
        return response

    def get_place_trends(self, woeid: int, count: int = 50) -> list[dict]:
        if not self.api_v1:
            self._init_user_auth()
        trends = self.api_v1.get_place_trends(woeid, count=count)
        units = 0
        if trends and trends[0]:
            units = len(trends[0].get("trends", []))
        log_api_usage(
            "user_read",
            units,
            "GET /1.1/trends/place",
            context="x_api_client.get_place_trends",
            metadata={"woeid": woeid, "count": count},
        )
        return trends

    def get_me(self) -> Any:
        """認証ユーザーの情報を取得（user_id キャッシュ用）"""
        if not self.client:
            self._init_user_auth()
        response = self.client.get_me()
        log_api_usage(
            "user_read",
            1,
            "GET /2/users/me",
            context="x_api_client.get_me",
        )
        return response

    # ---- bearer endpoints ----
    def _bearer_headers(self) -> dict[str, str]:
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN が未設定")
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def search_recent_tweets(self, query: str, max_results: int = 10) -> dict:
        url = "https://api.x.com/2/tweets/search/recent"
        safe_max_results = max(10, min(max_results, 100))
        params = {
            "query": f"{query} -is:retweet -is:reply lang:ja",
            "max_results": safe_max_results,
            "tweet.fields": "author_id,created_at,public_metrics",
            "expansions": "author_id",
            "user.fields": "username,public_metrics",
        }
        resp = requests.get(url, headers=self._bearer_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        tweets = data.get("data", []) or []
        users = data.get("includes", {}).get("users", []) or []
        log_api_usage(
            "post_read",
            len(tweets),
            "GET /2/tweets/search/recent",
            context="x_api_client.search_recent_tweets",
            metadata={"query": query, "max_results": params["max_results"]},
        )
        if users:
            log_api_usage(
                "user_read",
                len(users),
                "GET /2/tweets/search/recent (includes.users)",
                context="x_api_client.search_recent_tweets",
                metadata={"query": query, "max_results": params["max_results"]},
            )
        return data

    def get_user_tweets(
        self,
        user_id: str,
        max_results: int = 100,
        since_id: Optional[str] = None,
    ) -> list[dict]:
        if not self.client:
            self._init_user_auth()
        params: dict[str, Any] = {
            "max_results": max(5, min(max_results, 100)),
            "tweet_fields": ["created_at", "public_metrics", "non_public_metrics", "in_reply_to_user_id", "referenced_tweets"],
            "exclude": ["retweets"],
        }
        if since_id:
            params["since_id"] = since_id
        response = self.client.get_users_tweets(user_id, user_auth=True, **params)
        data = response.data or []
        log_api_usage(
            "post_read",
            len(data),
            f"GET /2/users/{user_id}/tweets",
            context="x_api_client.get_user_tweets",
            metadata={"max_results": params["max_results"], "since_id": since_id},
        )
        return data

    def get_tweets_public_metrics(self, tweet_ids: list[str]) -> Any:
        if not self.bearer_token:
            raise ValueError("X_BEARER_TOKEN が未設定")
        client = tweepy.Client(bearer_token=self.bearer_token)
        response = client.get_tweets(tweet_ids, tweet_fields=["public_metrics"])
        resource_count = len(response.data or []) if response else 0
        log_api_usage(
            "post_read",
            resource_count,
            "GET /2/tweets",
            context="x_api_client.get_tweets_public_metrics",
            metadata={"requested_ids": len(tweet_ids)},
        )
        return response
