import json
from typing import Any

from composer.models import (
    EnvironmentContext,
    WorkflowConnection,
    WorkflowNode,
    WorkflowSpec,
)


class N8nNodeAdapter:
    """
    Bidirectional translation between Composer nodes and n8n nodes.

    AutoWFBench capabilities are represented as n8n HTTP Request
    nodes that call the run-scoped environment /tools endpoint.
    """

    # =========================================================
    # COMPOSER -> N8N
    # =========================================================

    def convert(
        self,
        node: WorkflowNode,
        position: list[int],
        environment: EnvironmentContext | None = None,
    ) -> dict[str, Any]:
        """Convert one approved Composer node into an n8n node."""

        if node.node_type == "trigger":
            return self._manual_trigger(
                node=node,
                position=position,
            )

        if environment is None:
            raise ValueError(
                "EnvironmentContext is required for action nodes."
            )

        if node.tool not in environment.capabilities:
            raise ValueError(
                f"Capability '{node.tool}' is not available "
                "in the current environment."
            )

        return self._environment_request(
            node=node,
            position=position,
            environment=environment,
        )

    @staticmethod
    def _manual_trigger(
        node: WorkflowNode,
        position: list[int],
    ) -> dict[str, Any]:
        return {
            "name": node.name,
            "type": "n8n-nodes-base.manualTrigger",
            "typeVersion": 1,
            "parameters": {},
            "position": position,
        }

    @staticmethod
    def _environment_request(
        node: WorkflowNode,
        position: list[int],
        environment: EnvironmentContext,
    ) -> dict[str, Any]:
        """
        Convert an AutoWFBench capability invocation into an
        executable n8n HTTP Request node.

        AutoWFBench expects:

        POST <base_url>/tools

        {
            "operation": "<capability>",
            "arguments": {...}
        }
        """

        if node.runtime_input or not environment.base_url or not environment.access_token:
            raise ValueError("Use run_benchmark_composer.py to compile run-scoped workflows and runtime inputs")
        base_url = environment.base_url.rstrip("/")
        tools_url = f"{base_url}/tools"

        request_body = {
            "operation": node.tool,
            "arguments": node.parameters,
        }

        return {
            "name": node.name,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 4.5,
            "parameters": {
                "method": "POST",
                "url": tools_url,
                "authentication": "none",
                "sendHeaders": True,
                "specifyHeaders": "keypair",
                "headerParameters": {
                    "parameters": [
                        {
                            "name": "Authorization",
                            "value": (
                                "Bearer "
                                + environment.access_token
                            ),
                        }
                    ]
                },
                "sendBody": True,
                "contentType": "json",
                "specifyBody": "json",
                "jsonBody": json.dumps(request_body),
                "options": {},
            },
            "position": position,
        }

    # =========================================================
    # N8N -> COMPOSER
    # =========================================================

    def from_n8n_result(
        self,
        result,
    ) -> WorkflowSpec:
        """Convert an MCP get_workflow_details result."""

        data = self._extract_json(result)

        workflow_data = data.get("workflow")

        if not workflow_data:
            raise ValueError(
                "n8n response did not contain workflow data."
            )

        return self.from_n8n_workflow(workflow_data)

    def from_n8n_workflow(
        self,
        workflow_data: dict[str, Any],
    ) -> WorkflowSpec:
        """
        Convert persisted n8n workflow state back into
        the Composer's WorkflowSpec.
        """

        raw_nodes = workflow_data.get("nodes", [])
        logical = [n for n in raw_nodes if n.get("notes", "").startswith("composer-v2:")]
        if logical:
            parsed = tuple(self._from_n8n_node(n) for n in logical)
            # Collapse compiler helper nodes, but recover edges from persisted
            # n8n connections rather than assuming the saved graph is linear.
            logical_ids = {n["name"]: model.id for n, model in zip(logical, parsed)}
            saved = workflow_data.get("connections", {})
            edges = []
            for name, source_id in logical_ids.items():
                todo = [target["node"] for group in saved.get(name, {}).get("main", []) for target in group]
                seen = set()
                while todo:
                    target = todo.pop()
                    if target in seen:
                        continue
                    seen.add(target)
                    if target in logical_ids:
                        edges.append(WorkflowConnection(source_id, logical_ids[target]))
                    else:
                        todo.extend(t["node"] for group in saved.get(target, {}).get("main", []) for t in group)
            return WorkflowSpec(name=workflow_data.get("name", "n8n-workflow"),
                description=workflow_data.get("description", "") or "",
                nodes=parsed, connections=tuple(edges))


        nodes = tuple(
            self._from_n8n_node(node)
            for node in raw_nodes
        )

        name_to_id = {
            node["name"]: node["id"]
            for node in raw_nodes
        }

        connections = self._from_n8n_connections(
            workflow_data.get("connections", {}),
            name_to_id,
        )

        return WorkflowSpec(
            name=workflow_data.get(
                "name",
                "n8n-workflow",
            ),
            description=(
                workflow_data.get(
                    "description",
                    "",
                )
                or ""
            ),
            nodes=nodes,
            connections=connections,
        )

    def _from_n8n_node(
        self,
        node: dict[str, Any],
    ) -> WorkflowNode:
        """Convert one persisted n8n node into a Composer node."""

        if node.get("notes", "").startswith("composer-v2:"):
            from composer.planner import WorkflowPlanner
            return WorkflowPlanner._parse_node(json.loads(node["notes"][len("composer-v2:"):]))
        n8n_type = node.get("type", "")

        if n8n_type == "n8n-nodes-base.manualTrigger":
            return WorkflowNode(
                id=node["id"],
                name=node["name"],
                node_type="trigger",
                tool=None,
                parameters={},
            )

        if n8n_type == "n8n-nodes-base.httpRequest":
            return self._from_environment_request(node)

        # Preserve unknown nodes instead of silently deleting them.
        return WorkflowNode(
            id=node["id"],
            name=node["name"],
            node_type="action",
            tool=None,
            parameters=node.get("parameters", {}),
        )

    @staticmethod
    def _from_environment_request(
        node: dict[str, Any],
    ) -> WorkflowNode:
        """
        Recover the AutoWFBench capability and arguments from
        an n8n HTTP Request node.
        """

        parameters = node.get("parameters", {})
        raw_body = parameters.get("jsonBody", "{}")

        operation = None
        arguments: dict[str, Any] = {}

        if isinstance(raw_body, dict):
            body = raw_body
        else:
            try:
                body = json.loads(raw_body)
            except (json.JSONDecodeError, TypeError):
                body = {}

        if isinstance(body, dict):
            operation = body.get("operation")

            raw_arguments = body.get("arguments", {})

            if isinstance(raw_arguments, dict):
                arguments = raw_arguments

        return WorkflowNode(
            id=node["id"],
            name=node["name"],
            node_type="action",
            tool=operation,
            parameters=arguments,
        )

    @staticmethod
    def _from_n8n_connections(
        connections_data: dict[str, Any],
        name_to_id: dict[str, str],
    ) -> tuple[WorkflowConnection, ...]:
        """Convert n8n name-based connections to Composer IDs."""

        connections: list[WorkflowConnection] = []

        for source_name, output_types in connections_data.items():
            source_id = name_to_id.get(source_name)

            if source_id is None:
                continue

            main_outputs = output_types.get("main", [])

            for output_group in main_outputs:
                if not output_group:
                    continue

                for target in output_group:
                    target_name = target.get("node")

                    if not target_name:
                        continue

                    target_id = name_to_id.get(target_name)

                    if target_id is None:
                        continue

                    connections.append(
                        WorkflowConnection(
                            source=source_id,
                            target=target_id,
                        )
                    )

        return tuple(connections)

    @staticmethod
    def _extract_json(
        result,
    ) -> dict[str, Any]:
        """Extract JSON from an MCP CallToolResult."""

        for content in result.content:
            if not hasattr(content, "text"):
                continue

            try:
                return json.loads(content.text)
            except json.JSONDecodeError:
                continue

        raise ValueError(
            "Could not extract JSON from n8n MCP response."
        )
