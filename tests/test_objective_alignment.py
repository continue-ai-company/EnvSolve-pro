from __future__ import annotations

from experiments.analyze_objective_alignment import aggregate, select_case_attempts


def test_aggregate_separates_recall_from_excess_constraints() -> None:
    cases = [
        {
            "complete": True,
            "official_pass": False,
            "official_unobserved_modules": ["missing"],
            "excess_internal_modules": ["runtime_only"],
            "runtime_only_modules": ["runtime_only"],
            "internal_unresolved_constraints": 2,
            "module_obligation_counts": {
                "official": 2,
                "official_static_overlap": 1,
                "internal_union": 3,
                "excess_internal": 2,
            },
        },
        {
            "complete": True,
            "official_pass": True,
            "official_unobserved_modules": [],
            "excess_internal_modules": ["non_scoring"],
            "runtime_only_modules": [],
            "internal_unresolved_constraints": 1,
            "module_obligation_counts": {
                "official": 0,
                "official_static_overlap": 0,
                "internal_union": 1,
                "excess_internal": 1,
            },
        },
    ]

    summary = aggregate(cases)

    assert summary["static_proxy_recall"] == 0.5
    assert summary["excess_internal_share"] == 0.75
    assert summary["cases_with_official_unobserved_modules"] == 1
    assert summary["cases_official_pass_despite_internal_unresolved"] == 1


def test_select_case_attempts_prefers_complete_replacement() -> None:
    attempts = [
        {
            "case_id": "case-a",
            "artifact_root": "/source/case-a",
            "complete": False,
            "incomplete_reason": "infrastructure",
        },
        {
            "case_id": "case-a",
            "artifact_root": "/replacement/case-a",
            "complete": True,
        },
    ]

    selected = select_case_attempts(attempts)

    assert len(selected) == 1
    assert selected[0]["artifact_root"] == "/replacement/case-a"
    assert selected[0]["attempt_resolution"]["attempt_count"] == 2
