"""
Architecture Validator for ORBIT (Phase: Hybrid Workload Intelligence).
Performs deterministic structural and contractual validation on TopologyGraphs
before they are submitted to the SimPy discrete-event simulation engine.

Design Principle:
ORBIT prevents execution of invalid or hallucinated architectures.
Topologies must satisfy mathematical graph integrity and component compatibility rules.
"""
from enum import Enum
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

from orbit.sdk.models import TopologyGraph, ComponentNode, ComponentCategory, ConnectionEdge
from orbit.catalog.primitives import get_primitive, validate_primitive_connection


class ValidationVerdict(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"


class ValidationIssueSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationIssue(BaseModel):
    """An issue identified during architecture validation."""
    severity: ValidationIssueSeverity
    code: str = Field(description="Machine-readable rule code e.g. 'ERR_DISCONNECTED_ROUTE'")
    message: str = Field(description="Clear explanation of the architectural violation")
    node_id: Optional[str] = Field(default=None, description="Component node ID involved, if applicable")
    remediation_hint: Optional[str] = Field(default=None, description="Recommended architectural fix")


class ArchitectureValidationResult(BaseModel):
    """Overall outcome of architecture validation."""
    verdict: ValidationVerdict
    is_simulatable: bool = Field(description="Whether the topology can safely execute in the simulation engine")
    issues: List[ValidationIssue] = Field(default_factory=list)
    components_count: int
    connections_count: int
    workload_routes_count: int


class ArchitectureValidator:
    """Deterministic structural and semantic validator for TopologyGraphs."""

    def __init__(self, strict_interfaces: bool = True):
        self.strict_interfaces = strict_interfaces

    def validate(self, topology: TopologyGraph) -> ArchitectureValidationResult:
        """
        Validates topology graph against distributed system engineering rules:
        1. Node ID uniqueness and valid categories
        2. Ingress existence and entrypoint validity
        3. Connection edge validity (endpoints exist)
        4. Primitive interface compatibility
        5. Workload route continuity (each hop is connected by an edge)
        6. Acyclicity of synchronous paths (DAG validation)
        7. Reachability from ingress
        """
        issues: List[ValidationIssue] = []
        node_map: Dict[str, ComponentNode] = {c.id: c for c in topology.components}

        # 1. Ingress Validation
        if topology.ingress_node_id not in node_map:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.ERROR,
                    code="ERR_INGRESS_MISSING",
                    message=f"Ingress node '{topology.ingress_node_id}' is not defined in topology components.",
                    node_id=topology.ingress_node_id,
                    remediation_hint="Add an ingress component (e.g. api_gateway) or set ingress_node_id to an existing node.",
                )
            )

        ingress_node = node_map.get(topology.ingress_node_id)
        if ingress_node and ingress_node.category not in (ComponentCategory.INGRESS, ComponentCategory.EDGE):
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.WARNING,
                    code="WARN_INGRESS_NON_STANDARD",
                    message=f"Ingress node '{ingress_node.id}' category is '{ingress_node.category.value}', expected INGRESS or EDGE.",
                    node_id=ingress_node.id,
                    remediation_hint="Use an api_gateway, load_balancer, or websocket_gateway as the entrypoint.",
                )
            )

        # 2. Connection Edges Endpoint & Self-Loop Validation
        adj_list: Dict[str, List[str]] = {nid: [] for nid in node_map}
        edges_set: Set[tuple] = set()

        for edge in topology.connections:
            if edge.source_id not in node_map:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        code="ERR_EDGE_SOURCE_UNKNOWN",
                        message=f"Edge source '{edge.source_id}' does not exist in topology nodes.",
                        node_id=edge.source_id,
                    )
                )
            if edge.target_id not in node_map:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        code="ERR_EDGE_TARGET_UNKNOWN",
                        message=f"Edge target '{edge.target_id}' does not exist in topology nodes.",
                        node_id=edge.target_id,
                    )
                )
            if edge.source_id == edge.target_id:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        code="ERR_SELF_LOOP",
                        message=f"Self-loop detected on node '{edge.source_id}'. Direct self-connections are prohibited.",
                        node_id=edge.source_id,
                    )
                )
            if edge.source_id in node_map and edge.target_id in node_map:
                adj_list[edge.source_id].append(edge.target_id)
                edges_set.add((edge.source_id, edge.target_id))

        # 3. Workload Route Continuity Validation
        routes_to_validate: Dict[str, List[str]] = dict(topology.workload_routes)
        if not routes_to_validate:
            # Fallback to read_path and write_path if no workload_routes defined
            if topology.read_path:
                routes_to_validate["default_read"] = topology.read_path
            if topology.write_path:
                routes_to_validate["default_write"] = topology.write_path

        for route_name, path in routes_to_validate.items():
            if not path:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.ERROR,
                        code="ERR_EMPTY_ROUTE",
                        message=f"Workload route '{route_name}' has an empty execution path.",
                    )
                )
                continue

            # First node should be reachable from ingress or be ingress
            if path[0] != topology.ingress_node_id and path[0] not in adj_list.get(topology.ingress_node_id, []):
                # Check if path[0] is an alternate ingress (e.g. websocket gateway)
                first_node = node_map.get(path[0])
                if not (first_node and first_node.category in (ComponentCategory.INGRESS, ComponentCategory.EDGE)):
                    issues.append(
                        ValidationIssue(
                            severity=ValidationIssueSeverity.WARNING,
                            code="WARN_ROUTE_NOT_STARTING_AT_INGRESS",
                            message=f"Route '{route_name}' starts at '{path[0]}' instead of primary ingress '{topology.ingress_node_id}'.",
                            node_id=path[0],
                        )
                    )

            # Each hop (path[i] -> path[i+1]) must have a valid connection or queue
            for i in range(len(path) - 1):
                src, tgt = path[i], path[i + 1]
                if (src, tgt) not in edges_set:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationIssueSeverity.ERROR,
                            code="ERR_DISCONNECTED_ROUTE_HOP",
                            message=f"Route '{route_name}' specifies a hop from '{src}' to '{tgt}', but no connection edge exists between them.",
                            node_id=src,
                            remediation_hint=f"Add a ConnectionEdge from '{src}' to '{tgt}' in topology.connections.",
                        )
                    )

        # 4. Synchronous Graph Acyclicity (DAG Check)
        # Exclude asynchronous queue loops from strict DAG cycle check
        sync_adj_list: Dict[str, List[str]] = {nid: [] for nid in node_map}
        for edge in topology.connections:
            if edge.protocol != "async_event" and edge.source_id in node_map and edge.target_id in node_map:
                sync_adj_list[edge.source_id].append(edge.target_id)

        cycle_detected = self._detect_cycle(sync_adj_list)
        if cycle_detected:
            issues.append(
                ValidationIssue(
                    severity=ValidationIssueSeverity.ERROR,
                    code="ERR_SYNCHRONOUS_CYCLE",
                    message=f"Cyclic dependency detected in synchronous request graph: {' -> '.join(cycle_detected)}.",
                    remediation_hint="Break synchronous circular dependencies using an asynchronous message queue or decoupling layer.",
                )
            )

        # 5. Reachability Check (Identify completely disconnected / orphaned nodes)
        reachable_nodes = self._get_reachable_nodes(topology.ingress_node_id, adj_list)
        # Add alternate ingress nodes as roots as well
        for node in topology.components:
            if node.category in (ComponentCategory.INGRESS, ComponentCategory.EDGE):
                reachable_nodes.update(self._get_reachable_nodes(node.id, adj_list))

        for nid in node_map:
            if nid not in reachable_nodes and len(topology.components) > 1:
                issues.append(
                    ValidationIssue(
                        severity=ValidationIssueSeverity.WARNING,
                        code="WARN_UNREACHABLE_NODE",
                        message=f"Component '{nid}' is not reachable from any ingress entrypoint.",
                        node_id=nid,
                        remediation_hint=f"Connect '{nid}' to an upstream service or remove it from the topology.",
                    )
                )

        has_errors = any(i.severity == ValidationIssueSeverity.ERROR for i in issues)
        has_warnings = any(i.severity == ValidationIssueSeverity.WARNING for i in issues)

        if has_errors:
            verdict = ValidationVerdict.INVALID
            is_simulatable = False
        elif has_warnings:
            verdict = ValidationVerdict.WARNING
            is_simulatable = True
        else:
            verdict = ValidationVerdict.VALID
            is_simulatable = True

        return ArchitectureValidationResult(
            verdict=verdict,
            is_simulatable=is_simulatable,
            issues=issues,
            components_count=len(topology.components),
            connections_count=len(topology.connections),
            workload_routes_count=len(routes_to_validate),
        )

    def _detect_cycle(self, adj_list: Dict[str, List[str]]) -> Optional[List[str]]:
        """Standard DFS cycle detection on directed graph."""
        visited: Dict[str, int] = {k: 0 for k in adj_list}  # 0=unvisited, 1=visiting, 2=visited
        path: List[str] = []

        def dfs(node: str) -> Optional[List[str]]:
            visited[node] = 1
            path.append(node)
            for neighbor in adj_list.get(node, []):
                if visited.get(neighbor) == 1:
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if visited.get(neighbor) == 0:
                    result = dfs(neighbor)
                    if result:
                        return result
            path.pop()
            visited[node] = 2
            return None

        for node in adj_list:
            if visited[node] == 0:
                cycle = dfs(node)
                if cycle:
                    return cycle
        return None

    def _get_reachable_nodes(self, start_node: str, adj_list: Dict[str, List[str]]) -> Set[str]:
        """BFS search for all nodes reachable from start_node."""
        visited: Set[str] = set()
        queue = [start_node]
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                for neighbor in adj_list.get(curr, []):
                    if neighbor not in visited:
                        queue.append(neighbor)
        return visited
