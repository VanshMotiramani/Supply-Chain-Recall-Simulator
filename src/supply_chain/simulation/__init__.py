"""
simulation — Block 5 Recall Simulation, Ground Truth Registry, and Pure Traceability.
"""

from supply_chain.simulation.config import RecallSimulationConfig
from supply_chain.simulation.ground_truth import (
    AnomalyRecord,
    AnomalyType,
    GroundTruthRegistry,
)
from supply_chain.simulation.models import (
    DiscrepancyCategory,
    DiscrepancyFinding,
    DiscrepancyReport,
    RecallMetricsResult,
    SimulationDataset,
    create_simulation_dataset,
)
from supply_chain.simulation.traceability import (
    BackwardDeliveryTrace,
    BackwardFinishedLotTrace,
    ForwardFinishedLotTrace,
    ForwardMaterialLotTrace,
    trace_backward_from_delivery,
    trace_backward_from_finished_lot,
    trace_forward_from_finished_lot,
    trace_forward_from_material_lot,
)

__all__ = [
    # Configuration
    "RecallSimulationConfig",
    # Ground Truth
    "AnomalyType",
    "AnomalyRecord",
    "GroundTruthRegistry",
    # Discrepancies & Reporting
    "DiscrepancyCategory",
    "DiscrepancyFinding",
    "DiscrepancyReport",
    # Metrics
    "RecallMetricsResult",
    # Simulation Dataset & Isolation
    "SimulationDataset",
    "create_simulation_dataset",
    # Traceability Results & Traversal Functions
    "ForwardMaterialLotTrace",
    "ForwardFinishedLotTrace",
    "BackwardDeliveryTrace",
    "BackwardFinishedLotTrace",
    "trace_forward_from_material_lot",
    "trace_forward_from_finished_lot",
    "trace_backward_from_delivery",
    "trace_backward_from_finished_lot",
]
