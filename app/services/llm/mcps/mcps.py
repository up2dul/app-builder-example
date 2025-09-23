from contextlib import AsyncExitStack
from typing import Any

from agents.mcp import MCPServerStdio
from loguru import logger


def get_context7_mcp_server() -> MCPServerStdio:
    return MCPServerStdio(
        params={
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": {"DEFAULT_MINIMUM_TOKENS": "10000"},
        }
    )


def get_livesearch_mcp_server() -> MCPServerStdio:
    return MCPServerStdio(
        params={
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp@latest"],
            "env": {"DEFAULT_MINIMUM_TOKENS": "10000"},
        }
    )


async def get_all_mcp_servers() -> list[MCPServerStdio]:
    return [
        get_context7_mcp_server(),
        get_livesearch_mcp_server(),
    ]


class MCPServersContext:
    def __init__(self) -> None:
        self.stack = None
        self.active_servers = None

    async def __aenter__(self) -> tuple[list[Any], AsyncExitStack[bool | None]]:
        servers = await get_all_mcp_servers()
        self.stack = AsyncExitStack()

        self.active_servers = []
        for server in servers:
            try:
                active_server = await self.stack.enter_async_context(server)
                self.active_servers.append(active_server)
            except Exception as e:
                logger.error(f"Failed to initialize MCP server {server}: {e}")
                continue

        return self.active_servers, self.stack

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.stack:
            await self.stack.aclose()


def get_mcp_servers_context() -> MCPServersContext:
    return MCPServersContext()
