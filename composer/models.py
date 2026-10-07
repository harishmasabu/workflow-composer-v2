from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CapabilityContract:
    """
    Describes an operation exposed by the execution environment.

    argument_schema describes the arguments required by the operation.
    The Composer uses this metadata for planning only.
    """

    name: str
    argument_schema: dict[str, Any] = field(default_factory=dict)
    description: str | None = None


@dataclass(frozen=True)
class RuntimeInput:
    """
    Describes data that must be resolved during workflow execution.
    """

    source_nodes: tuple[str, ...]
    instruction: str


@dataclass(frozen=True)
class WorkflowNode:
    """Represents one approved step in a workflow."""

    id: str
    name: str
    node_type: str
    tool: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    runtime_input: RuntimeInput | None = None


@dataclass(frozen=True)
class WorkflowConnection:
    """Represents a directed edge between two workflow nodes."""

    source: str
    target: str


@dataclass(frozen=True)
class WorkflowSpec:
    """Engine-independent definition of the approved workflow."""

    name: str
    description: str
    nodes: tuple[WorkflowNode, ...]
    connections: tuple[WorkflowConnection, ...]

    def node_ids(self) -> set[str]:
        return {node.id for node in self.nodes}

    def get_node(self, node_id: str) -> WorkflowNode | None:
        return next(
            (node for node in self.nodes if node.id == node_id),
            None,
        )


@dataclass(frozen=True)
class NodeProposal:
    """One node proposed by the Composer but not yet approved."""

    node: WorkflowNode
    reason: str
    connect_from: str | None = None


@dataclass(frozen=True)
class RejectedProposal:
    """Records a rejected proposal and optional user feedback."""

    proposal: NodeProposal
    feedback: str | None = None


@dataclass(frozen=True)
class EnvironmentContext:
    """
    Run-scoped execution context supplied by AutoWFBench.

    Execution secrets stay outside the planning model.
    Capability contracts describe what operations are available
    and what arguments they require.
    """

    base_url: str
    access_token: str
    capability_contracts: tuple[CapabilityContract, ...]

    @property
    def capabilities(self) -> tuple[str, ...]:
        """
        Backwards-compatible view used by the validator and adapter.
        """
        return tuple(
            contract.name
            for contract in self.capability_contracts
        )

    def get_capability(
        self,
        name: str,
    ) -> CapabilityContract | None:
        return next(
            (
                contract
                for contract in self.capability_contracts
                if contract.name == name
            ),
            None,
        )


@dataclass(frozen=True)
class ComposerState:
    """State required to propose the next workflow node."""

    task: str
    workflow: WorkflowSpec
    environment: EnvironmentContext | None = None
    rejected_proposals: tuple[RejectedProposal, ...] = ()
    is_complete: bool = False
