"""Deterministic mock model server (OpenAI-compatible /chat/completions)."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from aiohttp import web


@dataclass
class MockResponse:
    """A scripted response from the mock model."""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    content: str = ""
    finish_reason: str = "tool_calls"


@dataclass
class Scenario:
    """A scripted scenario of turns and expected tool calls."""
    name: str
    turns: List[MockResponse] = field(default_factory=list)
    current_turn: int = 0

    def next_response(self) -> MockResponse:
        """Get the next scripted response."""
        if self.current_turn < len(self.turns):
            resp = self.turns[self.current_turn]
            self.current_turn += 1
            return resp
        # Default: stop
        return MockResponse(content="Done", finish_reason="stop")


class MockServer:
    """OpenAI-compatible mock server for conformance testing."""

    def __init__(self, scenario: Scenario, port: int = 12345):
        self.scenario = scenario
        self.port = port
        self.app = web.Application()
        self.app.router.add_post("/v1/chat/completions", self.handle_completions)
        self.runner: Optional[web.AppRunner] = None
        self.received_requests: List[Dict[str, Any]] = []

    async def handle_completions(self, request: web.Request) -> web.Response:
        body = await request.json()
        self.received_requests.append(body)

        response = self.scenario.next_response()

        # Build OpenAI-compatible response
        message = {
            "role": "assistant",
            "content": response.content,
        }
        if response.tool_calls:
            message["tool_calls"] = response.tool_calls

        return web.json_response({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "mock-model",
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": response.finish_reason,
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "localhost", self.port)
        await site.start()

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()

    def get_requests(self) -> List[Dict[str, Any]]:
        return self.received_requests
