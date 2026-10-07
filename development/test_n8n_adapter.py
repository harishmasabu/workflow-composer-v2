import asyncio

from adapters.n8n_node_adapter import N8nNodeAdapter
from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"


async def main():
    client = N8nMCPClient()
    adapter = N8nNodeAdapter()

    print("\nReading workflow from n8n...")

    result = await client.get_workflow_details(
        WORKFLOW_ID
    )

    workflow = adapter.from_n8n_result(
        result
    )

    print("\nCOMPOSER WORKFLOW STATE")
    print("-" * 50)

    print(f"Name: {workflow.name}")
    print(f"Description: {workflow.description}")

    print("\nNodes:")

    for node in workflow.nodes:
        print(f"  ID: {node.id}")
        print(f"  Name: {node.name}")
        print(f"  Type: {node.node_type}")
        print(f"  Tool: {node.tool}")
        print()

    print(
        f"Connections: "
        f"{len(workflow.connections)}"
    )


if __name__ == "__main__":
    asyncio.run(main())