from experiments.analyze_causal_frontier import aggregate


def test_aggregate_reports_surface_compression_without_effectiveness_claim() -> None:
    cases = [
        {
            "frontier": {
                "summary": {
                    "surface_module_obligation_count": 5,
                    "causally_grouped_surface_constraint_count": 4,
                    "maximum_surface_amplification": 4,
                },
                "causal_roots": [
                    {
                        "root_kind": "runtime_missing_dependency",
                        "surface_constraint_count": 4,
                    },
                    {"root_kind": "runtime_compatibility_frontier"},
                ],
            },
            "historical_raw_runtime_compatibility_findings": [{"finding": {}}],
        }
    ]

    result = aggregate(cases)

    assert result["case_count"] == 1
    assert result["module_causal_root_count"] == 1
    assert result["grouped_surface_constraints_per_module_root"] == 4.0
    assert result["cases_with_surface_amplification"] == 1
    assert result["historical_raw_runtime_compatibility_findings"] == 1
