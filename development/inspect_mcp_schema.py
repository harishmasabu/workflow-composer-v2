import asyncio
import os

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    load_dotenv(".env")

    url = os.getenv("N8N_MCP_URL")
    token = os.getenv("N8N_MCP_TOKEN")

    headers = {
        "Authorization": f"Bearer {token}",
    }

    timeout = httpx2.Timeout(
        30.0,
        read=300.0,
    )

    async with httpx2.AsyncClient(
        headers=headers,
        timeout=timeout,
    ) as http_client:

        async with streamable_http_client(
            url,
            http_client=http_client,
        ) as (read_stream, write_stream):

            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:

                await session.initialize()

                result = await session.list_tools()

                for tool in result.tools:
                    if tool.name in {
                        "get_node_types",
                        "validate_node_config",
                    }:
                        print(f"\n=== {tool.name} ===")
                        print(tool.input_schema)


if __name__ == "__main__":
    asyncio.run(main())
