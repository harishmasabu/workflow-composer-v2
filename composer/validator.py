from dataclasses import dataclass

from composer.models import WorkflowSpec


ALLOWED_NODE_TYPES = {"trigger", "action", "ai"}


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    errors: tuple[str, ...]


class WorkflowValidator:
    """Validates workflow structure and run-scoped capabilities."""

    def validate(
        self,
        workflow: WorkflowSpec,
        capabilities: tuple[str, ...] | None = None,
    ) -> ValidationResult:
        errors: list[str] = []

        self._validate_nodes(workflow, errors, capabilities)
        self._validate_connections(workflow, errors)
        self._validate_trigger(workflow, errors)
        self._validate_runtime(workflow, errors)

        return ValidationResult(
            is_valid=not errors,
            errors=tuple(errors),
        )

    def _validate_nodes(
        self,
        workflow: WorkflowSpec,
        errors: list[str],
        capabilities: tuple[str, ...] | None,
    ) -> None:
        seen_ids: set[str] = set()

        for node in workflow.nodes:
            if node.id in seen_ids:
                errors.append(f"Duplicate node ID: {node.id}")

            seen_ids.add(node.id)

            if node.node_type not in ALLOWED_NODE_TYPES:
                errors.append(
                    f"Unsupported node type '{node.node_type}' "
                    f"for node '{node.id}'"
                )

            if node.node_type == "trigger":
                if node.tool is not None:
                    errors.append(
                        f"Trigger node '{node.id}' must not specify a tool"
                    )
                continue

            if node.tool is None:
                errors.append(
                    f"Action node '{node.id}' must specify a capability"
                )
                continue

            if capabilities is not None and node.tool not in capabilities and not (node.node_type == "ai" and node.tool == "summary"):
                errors.append(
                    f"Capability '{node.tool}' is not available "
                    f"for node '{node.id}'"
                )

    def _validate_connections(
        self,
        workflow: WorkflowSpec,
        errors: list[str],
    ) -> None:
        node_ids = workflow.node_ids()

        for connection in workflow.connections:
            if connection.source not in node_ids:
                errors.append(
                    f"Connection source '{connection.source}' does not exist"
                )

            if connection.target not in node_ids:
                errors.append(
                    f"Connection target '{connection.target}' does not exist"
                )

    def _validate_trigger(
        self,
        workflow: WorkflowSpec,
        errors: list[str],
    ) -> None:
        triggers = [
            node
            for node in workflow.nodes
            if node.node_type == "trigger"
        ]

        if len(triggers) != 1:
            errors.append(
                "Workflow must contain exactly one trigger node"
            )

    def _validate_runtime(self, workflow, errors):
        parents = {node.id: set() for node in workflow.nodes}
        for edge in workflow.connections:
            if edge.target in parents:
                parents[edge.target].add(edge.source)
        for node in workflow.nodes:
            ancestors, todo = set(), list(parents[node.id])
            while todo:
                current = todo.pop()
                if current in ancestors:
                    continue
                ancestors.add(current)
                todo.extend(parents.get(current, ()))
            if node.id in ancestors:
                errors.append(f"Cycle at {node.id}")
            if node.runtime_input:
                if not node.runtime_input.instruction.strip():
                    errors.append(f"Missing runtime instruction: {node.id}")
                for source in node.runtime_input.source_nodes:
                    if source not in ancestors:
                        errors.append(f"Runtime source {source} is not upstream of {node.id}")
