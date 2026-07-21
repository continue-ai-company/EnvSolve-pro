from __future__ import annotations

from collections.abc import Callable

from envsolve_harness.adapters.base import BenchmarkAdapter
from envsolve_harness.core.models import HarnessConfig
from envsolve_harness.core.protocol import ExperimentProtocol
from envsolve.runtime.workspace import WorkspacePrecondition


AdapterFactory = Callable[[HarnessConfig, ExperimentProtocol], BenchmarkAdapter]
_FACTORIES: dict[str, AdapterFactory] = {}


def register_benchmark_adapter(adapter_id: str, factory: AdapterFactory) -> None:
    if adapter_id in _FACTORIES:
        raise ValueError(f"Benchmark adapter {adapter_id!r} is already registered")
    _FACTORIES[adapter_id] = factory


def _load_builtin_adapters() -> None:
    if "envbench" not in _FACTORIES:
        from envsolve_harness.adapters.envbench import EnvBenchEvaluator

        register_benchmark_adapter("envbench", EnvBenchEvaluator)


def registered_benchmark_adapters() -> tuple[str, ...]:
    _load_builtin_adapters()
    return tuple(sorted(_FACTORIES))


def create_benchmark_adapter(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
) -> BenchmarkAdapter:
    _load_builtin_adapters()
    benchmark = config.benchmark(protocol.benchmark)
    try:
        factory = _FACTORIES[benchmark.adapter]
    except KeyError as exc:
        raise ValueError(f"Unknown benchmark adapter: {benchmark.adapter!r}") from exc
    return factory(config, protocol)


def workspace_preconditions_for(
    config: HarnessConfig,
    protocol: ExperimentProtocol,
) -> tuple[WorkspacePrecondition, ...]:
    """Return adapter-owned setup state; unknown test adapters have no declaration."""

    _load_builtin_adapters()
    benchmark = config.benchmark(protocol.benchmark)
    factory = _FACTORIES.get(benchmark.adapter)
    if factory is None:
        return ()
    adapter = factory(config, protocol)
    return tuple(getattr(adapter, "workspace_preconditions", ()))
