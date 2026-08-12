from experiments.qualify_certification_repair_boundary_v2 import (
    repository_effect_audit,
)


def test_repository_effect_audit_accepts_raw_and_adapted_detail_shapes() -> None:
    raw = {"repository_effect_audit": {"valid": True, "policy": "v6"}}
    adapted = {
        "report_details": {
            "repository_effect_audit": {"valid": True, "policy": "v6"}
        }
    }

    assert repository_effect_audit(raw) == raw["repository_effect_audit"]
    assert repository_effect_audit(adapted) == adapted["report_details"][
        "repository_effect_audit"
    ]
    assert repository_effect_audit({}) is None
