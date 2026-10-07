import json
import os

from dotenv import load_dotenv
from groq import Groq

from composer.models import (
    ComposerState,
    NodeProposal,
    RuntimeInput,
    WorkflowConnection,
    WorkflowNode,
    WorkflowSpec,
)
from composer.prompts import (
    NEXT_NODE_PROMPT,
    SYSTEM_PROMPT,
)


class PlannerError(Exception):
    """Raised when the planner cannot produce a valid workflow response."""


class WorkflowPlanner:
    """Uses an LLM to compose workflows from natural-language tasks."""

    def __init__(self, model: str = "openai/gpt-oss-120b") -> None:
        load_dotenv(".env")

        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise PlannerError("GROQ_API_KEY is not configured")

        self.client = Groq(api_key=api_key)
        self.model = model

    def generate(self, task: str) -> WorkflowSpec:
        """
        Generate an entire workflow.

        Kept for backwards compatibility with the original Composer.
        """

        if not task.strip():
            raise PlannerError("Task cannot be empty")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + "\nYou MUST return a valid JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": task,
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        if not content:
            raise PlannerError("LLM returned an empty response")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlannerError(
                "LLM returned invalid JSON"
            ) from exc

        return self._to_workflow_spec(data)

    def propose_next(
        self,
        state: ComposerState,
    ) -> NodeProposal | None:
        """
        Propose exactly one next node.

        Only capability names and approved workflow state are exposed
        to the LLM. Execution secrets remain outside the model.
        """

        if not state.task.strip():
            raise PlannerError("Task cannot be empty")

        approved_nodes = [
            self._node_to_dict(node)
            for node in state.workflow.nodes
        ]

        approved_connections = [
            {
                "source": connection.source,
                "target": connection.target,
            }
            for connection in state.workflow.connections
        ]

        rejected_proposals = [
            {
                "node": self._node_to_dict(
                    rejected.proposal.node
                ),
                "reason": rejected.proposal.reason,
                "feedback": rejected.feedback,
            }
            for rejected in state.rejected_proposals
        ]

        available_capabilities = (
    [
        {
            "name": contract.name,
            "arguments": contract.argument_schema,
            "description": contract.description,
        }
        for contract in state.environment.capability_contracts
    ]
    if state.environment
    else []
)

        context = {
            "task": state.task,
            "available_capabilities": available_capabilities,
            "current_workflow": {
                "name": state.workflow.name,
                "description": state.workflow.description,
                "nodes": approved_nodes,
                "connections": approved_connections,
            },
            "rejected_proposals": rejected_proposals,
        }

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        NEXT_NODE_PROMPT
                        + "\nYou MUST return a valid JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        context,
                        indent=2,
                    ),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content

        if not content:
            raise PlannerError("LLM returned an empty response")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlannerError(
                "LLM returned invalid JSON"
            ) from exc

        if data.get("is_complete"):
            return None

        node_data = data.get("node")

        if not node_data:
            raise PlannerError(
                "LLM did not return a node proposal"
            )

        try:
            node = self._parse_node(node_data)

            return NodeProposal(
                node=node,
                reason=data["reason"],
                connect_from=data.get("connect_from"),
            )

        except (KeyError, TypeError, ValueError) as exc:
            raise PlannerError(
                "LLM response does not match NodeProposal"
            ) from exc

    @staticmethod
    def _parse_runtime_input(
        data: dict | None,
    ) -> RuntimeInput | None:
        if data is None:
            return None

        source_nodes = data.get("source_nodes")
        instruction = data.get("instruction")

        if not isinstance(source_nodes, list):
            raise ValueError(
                "runtime_input.source_nodes must be a list"
            )

        if not source_nodes:
            raise ValueError(
                "runtime_input.source_nodes cannot be empty"
            )

        if not all(
            isinstance(node_id, str) and node_id
            for node_id in source_nodes
        ):
            raise ValueError(
                "runtime_input.source_nodes must contain node IDs"
            )

        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError(
                "runtime_input.instruction is required"
            )

        return RuntimeInput(
            source_nodes=tuple(source_nodes),
            instruction=instruction.strip(),
        )

    @classmethod
    def _parse_node(
        cls,
        node_data: dict,
    ) -> WorkflowNode:
        runtime_input = cls._parse_runtime_input(
            node_data.get("runtime_input")
        )

        parameters = node_data.get("parameters", {})

        if not isinstance(parameters, dict):
            raise ValueError(
                "node.parameters must be an object"
            )

        return WorkflowNode(
            id=node_data["id"],
            name=node_data["name"],
            node_type=node_data["node_type"],
            tool=node_data.get("tool"),
            parameters=parameters,
            runtime_input=runtime_input,
        )

    @staticmethod
    def _node_to_dict(
        node: WorkflowNode,
    ) -> dict:
        runtime_input = None

        if node.runtime_input is not None:
            runtime_input = {
                "source_nodes": list(
                    node.runtime_input.source_nodes
                ),
                "instruction": (
                    node.runtime_input.instruction
                ),
            }

        return {
            "id": node.id,
            "name": node.name,
            "node_type": node.node_type,
            "tool": node.tool,
            "parameters": node.parameters,
            "runtime_input": runtime_input,
        }

    @classmethod
    def _to_workflow_spec(
        cls,
        data: dict,
    ) -> WorkflowSpec:
        """Convert LLM JSON into a WorkflowSpec."""

        try:
            nodes = tuple(
                cls._parse_node(node)
                for node in data["nodes"]
            )

            connections = tuple(
                WorkflowConnection(
                    source=connection["source"],
                    target=connection["target"],
                )
                for connection in data["connections"]
            )

            return WorkflowSpec(
                name=data["name"],
                description=data["description"],
                nodes=nodes,
                connections=connections,
            )

        except (KeyError, TypeError, ValueError) as exc:
            raise PlannerError(
                "LLM response does not match WorkflowSpec"
            ) from exc
