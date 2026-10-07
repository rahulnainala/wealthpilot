from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class HealthRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class HealthResponse(_message.Message):
    __slots__ = ("status",)
    STATUS_FIELD_NUMBER: _ClassVar[int]
    status: str
    def __init__(self, status: _Optional[str] = ...) -> None: ...

class GoalSleeve(_message.Message):
    __slots__ = ("bucket", "value", "annual_return_mean", "annual_return_volatility")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ANNUAL_RETURN_MEAN_FIELD_NUMBER: _ClassVar[int]
    ANNUAL_RETURN_VOLATILITY_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    value: float
    annual_return_mean: float
    annual_return_volatility: float
    def __init__(self, bucket: _Optional[str] = ..., value: _Optional[float] = ..., annual_return_mean: _Optional[float] = ..., annual_return_volatility: _Optional[float] = ...) -> None: ...

class GoalSimRequest(_message.Message):
    __slots__ = ("sleeves", "monthly_contribution", "months_remaining", "target_value", "num_paths", "seed", "initial_shock")
    SLEEVES_FIELD_NUMBER: _ClassVar[int]
    MONTHLY_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    MONTHS_REMAINING_FIELD_NUMBER: _ClassVar[int]
    TARGET_VALUE_FIELD_NUMBER: _ClassVar[int]
    NUM_PATHS_FIELD_NUMBER: _ClassVar[int]
    SEED_FIELD_NUMBER: _ClassVar[int]
    INITIAL_SHOCK_FIELD_NUMBER: _ClassVar[int]
    sleeves: _containers.RepeatedCompositeFieldContainer[GoalSleeve]
    monthly_contribution: float
    months_remaining: int
    target_value: float
    num_paths: int
    seed: int
    initial_shock: float
    def __init__(self, sleeves: _Optional[_Iterable[_Union[GoalSleeve, _Mapping]]] = ..., monthly_contribution: _Optional[float] = ..., months_remaining: _Optional[int] = ..., target_value: _Optional[float] = ..., num_paths: _Optional[int] = ..., seed: _Optional[int] = ..., initial_shock: _Optional[float] = ...) -> None: ...

class GoalSimResponse(_message.Message):
    __slots__ = ("probability_of_success", "median_ending_value", "p10_value", "p90_value")
    PROBABILITY_OF_SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_ENDING_VALUE_FIELD_NUMBER: _ClassVar[int]
    P10_VALUE_FIELD_NUMBER: _ClassVar[int]
    P90_VALUE_FIELD_NUMBER: _ClassVar[int]
    probability_of_success: float
    median_ending_value: float
    p10_value: float
    p90_value: float
    def __init__(self, probability_of_success: _Optional[float] = ..., median_ending_value: _Optional[float] = ..., p10_value: _Optional[float] = ..., p90_value: _Optional[float] = ...) -> None: ...

class BucketRisk(_message.Message):
    __slots__ = ("bucket", "value", "returns")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    RETURNS_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    value: float
    returns: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, bucket: _Optional[str] = ..., value: _Optional[float] = ..., returns: _Optional[_Iterable[float]] = ...) -> None: ...

class PortfolioRiskRequest(_message.Message):
    __slots__ = ("buckets", "confidence", "periods_per_year")
    BUCKETS_FIELD_NUMBER: _ClassVar[int]
    CONFIDENCE_FIELD_NUMBER: _ClassVar[int]
    PERIODS_PER_YEAR_FIELD_NUMBER: _ClassVar[int]
    buckets: _containers.RepeatedCompositeFieldContainer[BucketRisk]
    confidence: float
    periods_per_year: float
    def __init__(self, buckets: _Optional[_Iterable[_Union[BucketRisk, _Mapping]]] = ..., confidence: _Optional[float] = ..., periods_per_year: _Optional[float] = ...) -> None: ...

class RiskContribution(_message.Message):
    __slots__ = ("bucket", "contribution")
    BUCKET_FIELD_NUMBER: _ClassVar[int]
    CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    bucket: str
    contribution: float
    def __init__(self, bucket: _Optional[str] = ..., contribution: _Optional[float] = ...) -> None: ...

class PortfolioRiskResponse(_message.Message):
    __slots__ = ("var", "cvar", "contributions", "annual_volatility", "max_drawdown")
    VAR_FIELD_NUMBER: _ClassVar[int]
    CVAR_FIELD_NUMBER: _ClassVar[int]
    CONTRIBUTIONS_FIELD_NUMBER: _ClassVar[int]
    ANNUAL_VOLATILITY_FIELD_NUMBER: _ClassVar[int]
    MAX_DRAWDOWN_FIELD_NUMBER: _ClassVar[int]
    var: float
    cvar: float
    contributions: _containers.RepeatedCompositeFieldContainer[RiskContribution]
    annual_volatility: float
    max_drawdown: float
    def __init__(self, var: _Optional[float] = ..., cvar: _Optional[float] = ..., contributions: _Optional[_Iterable[_Union[RiskContribution, _Mapping]]] = ..., annual_volatility: _Optional[float] = ..., max_drawdown: _Optional[float] = ...) -> None: ...

class PortfolioProjectionRequest(_message.Message):
    __slots__ = ("sleeves", "monthly_contribution", "months", "num_paths", "seed")
    SLEEVES_FIELD_NUMBER: _ClassVar[int]
    MONTHLY_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    MONTHS_FIELD_NUMBER: _ClassVar[int]
    NUM_PATHS_FIELD_NUMBER: _ClassVar[int]
    SEED_FIELD_NUMBER: _ClassVar[int]
    sleeves: _containers.RepeatedCompositeFieldContainer[GoalSleeve]
    monthly_contribution: float
    months: int
    num_paths: int
    seed: int
    def __init__(self, sleeves: _Optional[_Iterable[_Union[GoalSleeve, _Mapping]]] = ..., monthly_contribution: _Optional[float] = ..., months: _Optional[int] = ..., num_paths: _Optional[int] = ..., seed: _Optional[int] = ...) -> None: ...

class ProjectionPoint(_message.Message):
    __slots__ = ("month", "p10", "median", "p90")
    MONTH_FIELD_NUMBER: _ClassVar[int]
    P10_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_FIELD_NUMBER: _ClassVar[int]
    P90_FIELD_NUMBER: _ClassVar[int]
    month: int
    p10: float
    median: float
    p90: float
    def __init__(self, month: _Optional[int] = ..., p10: _Optional[float] = ..., median: _Optional[float] = ..., p90: _Optional[float] = ...) -> None: ...

class PortfolioProjectionResponse(_message.Message):
    __slots__ = ("points",)
    POINTS_FIELD_NUMBER: _ClassVar[int]
    points: _containers.RepeatedCompositeFieldContainer[ProjectionPoint]
    def __init__(self, points: _Optional[_Iterable[_Union[ProjectionPoint, _Mapping]]] = ...) -> None: ...

class RetirementPlanRequest(_message.Message):
    __slots__ = ("sleeves", "contribution_schedule", "monthly_contribution", "accumulation_months", "target_value", "withdrawal_schedule", "drawdown_months", "num_paths", "seed")
    SLEEVES_FIELD_NUMBER: _ClassVar[int]
    CONTRIBUTION_SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    MONTHLY_CONTRIBUTION_FIELD_NUMBER: _ClassVar[int]
    ACCUMULATION_MONTHS_FIELD_NUMBER: _ClassVar[int]
    TARGET_VALUE_FIELD_NUMBER: _ClassVar[int]
    WITHDRAWAL_SCHEDULE_FIELD_NUMBER: _ClassVar[int]
    DRAWDOWN_MONTHS_FIELD_NUMBER: _ClassVar[int]
    NUM_PATHS_FIELD_NUMBER: _ClassVar[int]
    SEED_FIELD_NUMBER: _ClassVar[int]
    sleeves: _containers.RepeatedCompositeFieldContainer[GoalSleeve]
    contribution_schedule: _containers.RepeatedScalarFieldContainer[float]
    monthly_contribution: float
    accumulation_months: int
    target_value: float
    withdrawal_schedule: _containers.RepeatedScalarFieldContainer[float]
    drawdown_months: int
    num_paths: int
    seed: int
    def __init__(self, sleeves: _Optional[_Iterable[_Union[GoalSleeve, _Mapping]]] = ..., contribution_schedule: _Optional[_Iterable[float]] = ..., monthly_contribution: _Optional[float] = ..., accumulation_months: _Optional[int] = ..., target_value: _Optional[float] = ..., withdrawal_schedule: _Optional[_Iterable[float]] = ..., drawdown_months: _Optional[int] = ..., num_paths: _Optional[int] = ..., seed: _Optional[int] = ...) -> None: ...

class RetirementPlanResponse(_message.Message):
    __slots__ = ("probability_of_success", "median_corpus", "p10_corpus", "p90_corpus", "depletion_probability", "median_depletion_month", "median_terminal_value", "bands")
    PROBABILITY_OF_SUCCESS_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_CORPUS_FIELD_NUMBER: _ClassVar[int]
    P10_CORPUS_FIELD_NUMBER: _ClassVar[int]
    P90_CORPUS_FIELD_NUMBER: _ClassVar[int]
    DEPLETION_PROBABILITY_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_DEPLETION_MONTH_FIELD_NUMBER: _ClassVar[int]
    MEDIAN_TERMINAL_VALUE_FIELD_NUMBER: _ClassVar[int]
    BANDS_FIELD_NUMBER: _ClassVar[int]
    probability_of_success: float
    median_corpus: float
    p10_corpus: float
    p90_corpus: float
    depletion_probability: float
    median_depletion_month: float
    median_terminal_value: float
    bands: _containers.RepeatedCompositeFieldContainer[ProjectionPoint]
    def __init__(self, probability_of_success: _Optional[float] = ..., median_corpus: _Optional[float] = ..., p10_corpus: _Optional[float] = ..., p90_corpus: _Optional[float] = ..., depletion_probability: _Optional[float] = ..., median_depletion_month: _Optional[float] = ..., median_terminal_value: _Optional[float] = ..., bands: _Optional[_Iterable[_Union[ProjectionPoint, _Mapping]]] = ...) -> None: ...

class DiversificationAsset(_message.Message):
    __slots__ = ("label", "weight", "returns")
    LABEL_FIELD_NUMBER: _ClassVar[int]
    WEIGHT_FIELD_NUMBER: _ClassVar[int]
    RETURNS_FIELD_NUMBER: _ClassVar[int]
    label: str
    weight: float
    returns: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, label: _Optional[str] = ..., weight: _Optional[float] = ..., returns: _Optional[_Iterable[float]] = ...) -> None: ...

class DiversificationRequest(_message.Message):
    __slots__ = ("assets",)
    ASSETS_FIELD_NUMBER: _ClassVar[int]
    assets: _containers.RepeatedCompositeFieldContainer[DiversificationAsset]
    def __init__(self, assets: _Optional[_Iterable[_Union[DiversificationAsset, _Mapping]]] = ...) -> None: ...

class CorrelatedPair(_message.Message):
    __slots__ = ("label_a", "label_b", "correlation")
    LABEL_A_FIELD_NUMBER: _ClassVar[int]
    LABEL_B_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_FIELD_NUMBER: _ClassVar[int]
    label_a: str
    label_b: str
    correlation: float
    def __init__(self, label_a: _Optional[str] = ..., label_b: _Optional[str] = ..., correlation: _Optional[float] = ...) -> None: ...

class DiversificationResponse(_message.Message):
    __slots__ = ("average_correlation", "diversification_ratio", "effective_holdings", "holdings", "top_pairs")
    AVERAGE_CORRELATION_FIELD_NUMBER: _ClassVar[int]
    DIVERSIFICATION_RATIO_FIELD_NUMBER: _ClassVar[int]
    EFFECTIVE_HOLDINGS_FIELD_NUMBER: _ClassVar[int]
    HOLDINGS_FIELD_NUMBER: _ClassVar[int]
    TOP_PAIRS_FIELD_NUMBER: _ClassVar[int]
    average_correlation: float
    diversification_ratio: float
    effective_holdings: float
    holdings: int
    top_pairs: _containers.RepeatedCompositeFieldContainer[CorrelatedPair]
    def __init__(self, average_correlation: _Optional[float] = ..., diversification_ratio: _Optional[float] = ..., effective_holdings: _Optional[float] = ..., holdings: _Optional[int] = ..., top_pairs: _Optional[_Iterable[_Union[CorrelatedPair, _Mapping]]] = ...) -> None: ...
