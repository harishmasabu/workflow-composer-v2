import asyncio

from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"
NODE_NAME = "Apply Checkout Service Patch"


async def main():
    client = N8nMCPClient()

    print(f"Removing node: {NODE_NAME}")

    result = await client._call_tool(
        "update_workflow",
        {
            "workflowId": WORKFLOW_ID,
            "operations": [
                {
                    "type": "removeNode",
                    "nodeName": NODE_NAME,
                }
            ],
            "versionName": "Remove old patch node",
            "versionDescription": (
                "Remove the old patch node so the upgraded "
                "Composer can regenerate it with runtime dependencies."
            ),
        },
    )

    client.print_result(result)


if __name__ == "__main__":
    asyncio.run(main())
