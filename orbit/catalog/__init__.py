"""
ORBIT Catalog Package.
Standardized catalogs for universal system archetypes and workload profile generation.
"""
from orbit.catalog.archetypes import (
    ArchetypeID,
    SystemArchetype,
    BaselineWorkloadAssumptions,
    ParameterRanges,
    SYSTEM_ARCHETYPE_CATALOG,
    get_archetype,
    list_archetypes,
    classify_workload_text,
)
from orbit.catalog.workload_profile import (
    ParameterProvenanceSource,
    ParameterProvenanceItem,
    TrafficProfile,
    OperationsProfile,
    DataProfile,
    PerformanceProfile,
    RequirementsProfile,
    ComputationProfile,
    WorkloadProfile,
    generate_workload_profile,
)

from orbit.catalog.primitives import (
    PrimitiveCategory,
    InfrastructurePrimitive,
    INFRASTRUCTURE_PRIMITIVE_CATALOG,
    get_primitive,
    list_primitives,
    validate_primitive_connection,
)

__all__ = [
    "ArchetypeID",
    "SystemArchetype",
    "BaselineWorkloadAssumptions",
    "ParameterRanges",
    "SYSTEM_ARCHETYPE_CATALOG",
    "get_archetype",
    "list_archetypes",
    "classify_workload_text",
    "ParameterProvenanceSource",
    "ParameterProvenanceItem",
    "TrafficProfile",
    "OperationsProfile",
    "DataProfile",
    "PerformanceProfile",
    "RequirementsProfile",
    "ComputationProfile",
    "WorkloadProfile",
    "generate_workload_profile",
    "PrimitiveCategory",
    "InfrastructurePrimitive",
    "INFRASTRUCTURE_PRIMITIVE_CATALOG",
    "get_primitive",
    "list_primitives",
    "validate_primitive_connection",
]
