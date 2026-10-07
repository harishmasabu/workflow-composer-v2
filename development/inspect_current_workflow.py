import asyncio
import json

from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"


async def main():
    client = N8nMCPClient()

    result = await client.get_workflow_details(WORKFLOW_ID)

    for content in result.content:
        if hasattr(content, "text"):
            try:
                data = json.loads(content.text)
                workflow = data.get("workflow", data)

                print("\n=== NODES ===")

                for node in workflow.get("nodes", []):
                    print()
                    print("ID:   ", node.get("id"))
                    print("Name: ", node.get("name"))
                    print("Type: ", node.get("type"))

                print("\n=== CONNECTIONS ===")
                print(
                    json.dumps(
                        workflow.get("connections", {}),
                        indent=2,
                    )
                )

            except json.JSONDecodeError:
                print(content.text)


if __name__ == "__main__":
    asyncio.run(main())
