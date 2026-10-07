import asyncio

from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"


async def main():
    client = N8nMCPClient()

    print("\nReading current workflow from n8n...\n")

    result = await client.get_workflow_details(
        WORKFLOW_ID
    )

    client.print_result(result)


if __name__ == "__main__":
    asyncio.run(main())