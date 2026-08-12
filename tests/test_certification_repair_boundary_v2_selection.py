from __future__ import annotations

from experiments.tools.select_pro_certification_repair_boundary_v2_dev8 import (
    SALT,
    _digest,
    _select_replacements,
)


def test_replacement_selection_is_identity_only_and_skips_consumed() -> None:
    rows = [
        {"repository": name, "case_id": f"case-{name}"}
        for name in ("owner/a", "owner/b", "owner/c", "owner/d")
    ]
    consumed = {"owner/b"}

    selected, remaining = _select_replacements(rows, consumed, take=2)

    expected = sorted(
        (row for row in rows if row["repository"] not in consumed),
        key=lambda row: _digest(SALT, row["repository"]),
    )
    assert selected == expected[:2]
    assert remaining == expected[2:]
    assert all(row["repository"] not in consumed for row in selected + remaining)
