import json
from pathlib import Path
import tempfile
import unittest

from envsolve.state import EventStore, EventType


CASE_ID = "owner/repo@abc"


class StateStoreTest(unittest.TestCase):
    def test_state_reconstructs_from_hash_chained_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "state.jsonl", CASE_ID)
            first = store.append(
                EventType.RUN_STARTED,
                {"case": {"case_id": CASE_ID, "repository": "owner/repo", "revision": "abc"}},
            )
            evidence = store.append(
                EventType.EVIDENCE_RECORDED,
                {
                    "evidence_id": "ev-python",
                    "kind": "python-requires",
                    "source": "pyproject.toml",
                    "value": ">=3.10",
                    "confidence": 1.0,
                },
            )
            store.append(
                EventType.CONSTRAINT_UPSERTED,
                {
                    "constraint_id": "python-version",
                    "kind": "runtime",
                    "expression": "python>=3.10",
                    "status": "active",
                    "evidence_ids": ["ev-python"],
                },
            )
            store.append(
                EventType.ACTION_PROPOSED,
                {
                    "action_id": "install",
                    "action_type": "package-install",
                    "command": "python -m pip install -e .",
                    "rationale": "Install declared dependencies",
                    "preconditions": ["python-version"],
                },
            )
            store.append(EventType.ACTION_STARTED, {"action_id": "install"})
            last = store.append(
                EventType.ACTION_FINISHED,
                {"action_id": "install", "exit_code": 0, "observation": "installed"},
            )

            state = store.reconstruct()
            self.assertEqual(first.sequence, 0)
            self.assertEqual(evidence.previous_hash, first.event_hash)
            self.assertEqual(state.last_event_hash, last.event_hash)
            self.assertEqual(state.constraints["python-version"]["status"], "active")
            self.assertEqual(state.constraints["python-version"]["state_metadata"]["revision"], 1)
            self.assertEqual(state.actions["install"]["status"], "succeeded")
            self.assertEqual(state.actions["install"]["state_metadata"]["revision"], 3)
            self.assertEqual(len(store.read()), 6)
            self.assertEqual(store.reconstruct().to_dict(), state.to_dict())
            self.assertRegex(state.to_dict()["snapshot_hash"], r"^[0-9a-f]{64}$")

    def test_tampered_payload_breaks_event_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.jsonl"
            store = EventStore(path, CASE_ID)
            store.append(
                EventType.RUN_STARTED,
                {"case": {"case_id": CASE_ID, "repository": "owner/repo", "revision": "abc"}},
            )
            record = json.loads(path.read_text())
            record["payload"]["case"]["revision"] = "tampered"
            path.write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                store.read()

    def test_invalid_transition_is_not_appended(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.jsonl"
            store = EventStore(path, CASE_ID)
            store.append(
                EventType.RUN_STARTED,
                {"case": {"case_id": CASE_ID, "repository": "owner/repo", "revision": "abc"}},
            )
            store.append(
                EventType.ACTION_PROPOSED,
                {
                    "action_id": "install",
                    "action_type": "package-install",
                    "command": "pip install -e .",
                    "rationale": "Install package",
                    "preconditions": [],
                },
            )
            before = path.read_text()
            with self.assertRaisesRegex(ValueError, "cannot finish"):
                store.append(
                    EventType.ACTION_FINISHED,
                    {"action_id": "install", "exit_code": 0, "observation": "installed"},
                )
            self.assertEqual(path.read_text(), before)

    def test_constraint_requires_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "state.jsonl", CASE_ID)
            store.append(
                EventType.RUN_STARTED,
                {"case": {"case_id": CASE_ID, "repository": "owner/repo", "revision": "abc"}},
            )
            with self.assertRaisesRegex(ValueError, "Unknown evidence"):
                store.append(
                    EventType.CONSTRAINT_UPSERTED,
                    {
                        "constraint_id": "python-version",
                        "kind": "runtime",
                        "expression": "python>=3.10",
                        "status": "active",
                        "evidence_ids": ["missing"],
                    },
                )

    def test_event_requires_integer_sequence_and_utc_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.jsonl"
            store = EventStore(path, CASE_ID)
            event = store.append(
                EventType.RUN_STARTED,
                {"case": {"case_id": CASE_ID, "repository": "owner/repo", "revision": "abc"}},
            ).to_dict()
            event["sequence"] = "0"
            path.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "sequence must be an integer"):
                store.read()
            event["sequence"] = 0
            event["timestamp"] = "2026-07-13T12:00:00"
            path.write_text(json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "UTC offset"):
                store.read()


if __name__ == "__main__":
    unittest.main()
