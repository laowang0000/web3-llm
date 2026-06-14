import unittest
from unittest.mock import patch

import httpx

from app.llm.ollama_client import ResearchApiChatClient, ResearchApiSettings


class FakeHttpClient:
    requests = []

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url, headers=None, json=None):
        request = httpx.Request("POST", url)
        self.requests.append(
            {
                "url": url,
                "headers": headers or {},
                "json": json or {},
                "timeout": self.timeout,
            }
        )
        return httpx.Response(
            200,
            request=request,
            json={
                "answer": "Remote answer",
                "conversation_id": "conversation-1",
                "status": "success",
            },
        )


class ResearchApiChatClientTests(unittest.TestCase):
    def setUp(self):
        FakeHttpClient.requests = []

    def test_chat_posts_only_raw_user_question_to_research_api_with_bearer_auth(self):
        client = ResearchApiChatClient(
            ResearchApiSettings(
                endpoint_url="http://100.124.37.113:5000/v1/research/ask",
                api_key="secret",
                model="remote-research-api",
            )
        )

        with patch("app.llm.ollama_client.httpx.Client", FakeHttpClient):
            answer = client.chat(
                message="Analyze BTC risk.",
                system_prompt="Use only provided context.",
                context="Market context",
            )

        self.assertEqual(answer, "Remote answer")
        self.assertEqual(len(FakeHttpClient.requests), 1)
        request = FakeHttpClient.requests[0]
        self.assertEqual(request["url"], "http://100.124.37.113:5000/v1/research/ask")
        self.assertEqual(request["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        self.assertEqual(request["json"]["question"], "Analyze BTC risk.")

    def test_list_models_uses_short_probe_and_returns_virtual_model(self):
        client = ResearchApiChatClient(
            ResearchApiSettings(
                endpoint_url="http://100.124.37.113:5000/v1/research/ask",
                api_key="secret",
                model="remote-research-api",
            )
        )

        with patch("app.llm.ollama_client.httpx.Client", FakeHttpClient):
            data = client.list_models()

        self.assertEqual(data["provider_type"], "research_api")
        self.assertEqual(data["available_models"], ["remote-research-api"])
        self.assertEqual(data["chat_models"], ["remote-research-api"])
        self.assertEqual(FakeHttpClient.requests[0]["json"]["question"], "Reply with OK only.")


if __name__ == "__main__":
    unittest.main()
