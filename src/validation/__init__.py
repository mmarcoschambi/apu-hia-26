"""
Validation Framework - Three-Phase Research Gate
===============================================

This package provides comprehensive validation for trading strategies
before they are promoted to production.

Modules:
    research_gate: Three-phase validation (Discovery → Validation → Productionization)
    stress_testing: Comprehensive stress test suite
    robustness_metrics: Robust objective functions for optimization

Usage:
    from src.validation import ResearchGate, StressTestSuite
    from src.validation.robustness_metrics import robust_objective_function

    # Validate strategy
    gate = ResearchGate()
    result = gate.validate_strategy(...)

    if result.promotion_approved:
        print("Strategy ready for production!")
"""

from src.validation.research_gate import (
    ResearchGate,
    ValidationThresholds,
    ValidationResult,
    validate_for_production,
)

from src.validation.stress_testing import (
    StressTestSuite,
    StressThresholds,
    StressTestResult,
    run_stress_test,
)

from src.validation.robustness_metrics import (
    RobustnessMetrics,
    RobustObjectiveConfig,
    robust_objective_function,
    calculate_comprehensive_robustness_report,
)

__all__ = [
    # Research Gate
    "ResearchGate",
    "ValidationThresholds",
    "ValidationResult",
    "validate_for_production",
    # Stress Testing
    "StressTestSuite",
    "StressThresholds",
    "StressTestResult",
    "run_stress_test",
    # Robustness Metrics
    "RobustnessMetrics",
    "RobustObjectiveConfig",
    "robust_objective_function",
    "calculate_comprehensive_robustness_report",
]

__version__ = "1.0.0"
