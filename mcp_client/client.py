import os

import httpx2
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


class N8nMCPClient:
    """
    Client for communicating with n8n's built-in MCP server.

    n8n is treated as the persistent workflow store.
    The Composer reads and updates workflows through MCP.
    """

    def __init__(self):
        load_dotenv(".env")

        self.url = os.getenv("N8N_MCP_URL")
        self.token = os.getenv("N8N_MCP_TOKEN")

        if not self.url:
            raise RuntimeError(
                "N8N_MCP_URL is not configured"
            )

        if not self.token:
            raise RuntimeError(
                "N8N_MCP_TOKEN is not configured"
            )

    def _get_headers(self) -> dict:
        """Return authentication headers for n8n MCP."""

        return {
            "Authorization": f"Bearer {self.token}",
        }

    def _get_timeout(self):
        """Return timeout configuration for MCP requests."""

        return httpx2.Timeout(
            30.0,
            read=300.0,
        )

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict,
    ):
        """
        Call an n8n MCP tool.

        All MCP communication goes through this helper.
        """

        async with httpx2.AsyncClient(
            headers=self._get_headers(),
            timeout=self._get_timeout(),
        ) as http_client:

            async with streamable_http_client(
                self.url,
                http_client=http_client,
            ) as (read_stream, write_stream):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await session.initialize()

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments,
                    )

                    return result

    @staticmethod
    def print_result(result):
        """Print text returned by an MCP tool."""

        for content in result.content:
            if hasattr(content, "text"):
                print(content.text)

    async def validate_workflow(
        self,
        workflow_code: str,
    ):
        """Validate Workflow SDK code using n8n."""

        result = await self._call_tool(
            "validate_workflow",
            {
                "code": workflow_code,
            },
        )

        print("\nCONNECTED TO N8N MCP ✓")
        print("\nVALIDATION RESULT\n")

        self.print_result(result)

        return result

    async def create_workflow(
        self,
        workflow_code: str,
        name: str = "Production Incident Recovery",
        description: str = (
            "Workflow composed interactively through "
            "the AI Workflow Composer."
        ),
    ):
        """
        Create a new n8n workflow after the first
        Composer node has been approved.
        """

        result = await self._call_tool(
            "create_workflow_from_code",
            {
                "code": workflow_code,
                "name": name,
                "description": description,
                "versionName": "Initial approved node",
                "versionDescription": (
                    "Created after the user approved "
                    "the first Composer proposal."
                ),
            },
        )

        print("\nCONNECTED TO N8N MCP ✓")
        print("\nCREATE WORKFLOW RESULT\n")

        self.print_result(result)

        return result

    async def get_workflow_details(
        self,
        workflow_id: str,
    ):
        """
        Read the current workflow directly from n8n.

        This allows the Composer to inspect what actually
        exists in n8n before proposing another node.
        """

        result = await self._call_tool(
            "get_workflow_details",
            {
                "workflowId": workflow_id,
            },
        )

        return result

    async def add_approved_node(
        self,
        workflow_id: str,
        node: dict,
        connect_from: str | None = None,
    ):
        """
        Add exactly one approved node to an existing
        n8n workflow.

        When connect_from is provided, the connection
        is created in the same atomic update.
        """

        operations = [
            {
                "type": "addNode",
                "node": node,
            }
        ]

        if connect_from:
            operations.append(
                {
                    "type": "addConnection",
                    "source": connect_from,
                    "target": node["name"],
                    "sourceIndex": 0,
                    "targetIndex": 0,
                    "connectionType": "main",
                }
            )

        result = await self._call_tool(
            "update_workflow",
            {
                "workflowId": workflow_id,
                "operations": operations,
                "versionName": (
                    f"Add {node['name']}"
                ),
                "versionDescription": (
                    "Added user-approved Composer node: "
                    f"{node['name']}"
                ),
            },
        )

        print(
            f"\n✓ Added '{node['name']}' to n8n"
        )

        return result

    async def inspect_update_workflow_tool(self):
        """Inspect n8n's update_workflow MCP tool."""

        async with httpx2.AsyncClient(
            headers=self._get_headers(),
            timeout=self._get_timeout(),
        ) as http_client:

            async with streamable_http_client(
                self.url,
                http_client=http_client,
            ) as (read_stream, write_stream):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await session.initialize()

                    result = await session.list_tools()

                    for tool in result.tools:
                        if tool.name == "update_workflow":
                            return tool

        raise RuntimeError(
            "update_workflow tool was not found"
        )

    async def inspect_search_nodes_tool(self):
        """Inspect n8n's search_nodes MCP tool."""

        async with httpx2.AsyncClient(
            headers=self._get_headers(),
            timeout=self._get_timeout(),
        ) as http_client:

            async with streamable_http_client(
                self.url,
                http_client=http_client,
            ) as (read_stream, write_stream):

                async with ClientSession(
                    read_stream,
                    write_stream,
                ) as session:

                    await session.initialize()

                    result = await session.list_tools()

                    for tool in result.tools:
                        if tool.name == "search_nodes":
                            return tool

        raise RuntimeError(
            "search_nodes tool was not found"
        )