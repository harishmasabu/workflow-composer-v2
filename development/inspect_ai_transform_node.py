import asyncio

from mcp_client.client import N8nMCPClient


async def main():
    client = N8nMCPClient()

    result = await client._call_tool(
        "get_node_types",
        {
            "nodeIds": [
                {
                    "nodeId": "n8n-nodes-base.aiTransform",
                    "version": "1",
                }
            ]
        },
    )

    client.print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
