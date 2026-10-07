import asyncio
import json

from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"


async def main():
    client = N8nMCPClient()

    result = await client.get_workflow_details(WORKFLOW_ID)

    for content in result.content:
        if not hasattr(content, "text"):
            continue

        try:
            data = json.loads(content.text)
        except json.JSONDecodeError:
            continue

        workflow = data.get("workflow", data)

        for node in workflow.get("nodes", []):
            if node.get("name") == "Apply Checkout Service Patch":
                print("\n=== APPLY CHECKOUT SERVICE PATCH ===")
                print(json.dumps(node, indent=2))
                return

    print("Patch node not found.")


if __name__ == "__main__":
    asyncio.run(main())
