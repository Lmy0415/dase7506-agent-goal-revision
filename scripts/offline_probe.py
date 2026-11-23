"""Verify write evidence and revised final-state scoring without a model."""

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from uuid import uuid4

from appworld import AppWorld
from appworld.collections.models import ModelCollectionPair
from appworld.evaluator import TestTracker

from scoring import Effect, WriteEvent, WriteOutcome, score


DATA_SHA256 = "4212365f457fda19dbb642888990e1dff2c63bb4a3724998d3ae2362a588a4c1"
SWAP = 85
DROP = 254


def load_cases(dataset):
    contents = dataset.read_bytes()
    if sha256(contents).hexdigest() != DATA_SHA256:
        raise ValueError("Use the pinned InterventionBench v1.1 AppWorld JSONL")
    rows = (json.loads(line) for line in contents.splitlines() if line)
    return {row["intervention_idx"]: row for row in rows if row["intervention_idx"] in (SWAP, DROP)}


def app_login(world, app):
    password = next(
        item["password"]
        for item in world.apis.supervisor.show_account_passwords()
        if item["account_name"] == app
    )
    username = world.task.supervisor.phone_number if app == "phone" else world.task.supervisor.email
    return world.apis[app]["login"](username=username, password=password)["access_token"]


def state_summary(world, case_id):
    if case_id == SWAP:
        return sorted(
            (row.id, row.time, row.label, row.enabled)
            for row in world.models.phone.Alarm.all()
        )
    return {
        "playlist_songs": sorted(
            (row.playlist_id, row.song_id) for row in world.models.spotify.PlaylistSong.all()
        ),
        "downloads": sorted(
            (row.user_id, row.song_id) for row in world.models.spotify.UserDownloadedSong.all()
        ),
    }


def digest(state):
    return sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def write(world, audit, case_id, app, tool, effect, access_token, **arguments):
    before = digest(state_summary(world, case_id))
    response = world.requester._request(
        app, tool, raise_on_failure=False, access_token=access_token, **arguments
    )
    after = digest(state_summary(world, case_id))
    if response.status_code == 200 and before != after:
        outcome = WriteOutcome.COMMITTED
    elif 400 <= response.status_code < 500 and before == after:
        outcome = WriteOutcome.REJECTED
    else:
        outcome = WriteOutcome.UNKNOWN
    event = WriteEvent(len(audit) + 1, effect, outcome)
    audit.append((event, {
        "sequence": event.sequence,
        "tool": f"{app}.{tool}",
        "arguments": arguments,
        "status": response.status_code,
        "before": before,
        "after": after,
        "outcome": outcome.value,
    }))
    return response.json()


def model_pair(world):
    task = world.task
    start = task.model_collection
    end = world.models
    return ModelCollectionPair(
        start_db_home_path=start.from_db_home_path,
        start_model_collection=start,
        end_db_home_path=end.to_db_home_path,
        end_model_collection=end,
    )


def evaluate_revised(world, case):
    task = world.task
    gt = task.ground_truth
    models = model_pair(world)
    namespace = {}
    exec(compile(case["evaluation_code"], f"intervention-{case['intervention_idx']}", "exec"), namespace)
    tracker = TestTracker(test_data=None, difficulty=gt.metadata["difficulty"], suppress_errors=True)
    namespace["evaluate"](
        test=tracker,
        public_data=gt.public_data,
        private_data=gt.private_data,
        main_user=models.start.admin.MainUser.find_one(**task.supervisor),
        models=models,
        ground_truth_answer=gt.answer,
    )
    return len(tracker.passes), len(tracker.failures)


def swap_branch(world, audit, token, transient):
    gt = world.task.ground_truth
    when = gt.private_data.alarm_time
    old = f"Flight to {gt.public_data.destination}"
    new = f"Pack for {gt.public_data.destination}"
    requested_label = old if transient else new
    created = write(
        world, audit, SWAP, "phone", "create_alarm",
        Effect("alarm.set_label", {"time": when, "label": requested_label}),
        token, time=when, label=requested_label,
    )
    if transient:
        write(
            world, audit, SWAP, "phone", "update_alarm",
            Effect("alarm.set_label", {"time": when, "label": new}),
            token, alarm_id=created["alarm_id"], label=new,
        )
    retained = any(
        row.id == created["alarm_id"] and row.time == when and row.enabled
        for row in world.models.phone.Alarm.all()
    )
    return Effect("alarm.set_label", {"time": when, "label": old}), {"alarm_time_and_enabled": retained}


def add_song(world, audit, token, playlist, song):
    write(
        world, audit, DROP, "spotify", "add_song_to_playlist",
        Effect("playlist.add_song", {"playlist_id": playlist, "song_id": song}),
        token, playlist_id=playlist, song_id=song,
    )


def drop_branch(world, audit, token, transient):
    data = world.task.ground_truth.private_data
    song_ids = data.song_ids_not_in_playlist
    if transient:
        playlist = world.models.spotify.Playlist.find_one(id=data.playlist_id)
        existing = {
            row.song_id
            for row in world.models.spotify.UserDownloadedSong.find_all(user_id=playlist.user_id)
        }
        song = next(
            song for song in data.song_ids_in_playlist + song_ids if song not in existing
        )
        write(
            world, audit, DROP, "spotify", "download_song",
            Effect("spotify.download_song", {"song_id": song}), token, song_id=song,
        )
        write(
            world, audit, DROP, "spotify", "remove_downloaded_song",
            Effect("spotify.remove_download", {"song_id": song}), token, song_id=song,
        )
    for song in song_ids[1:]:
        add_song(world, audit, token, data.playlist_id, song)
    present = {
        row.song_id
        for row in world.models.spotify.PlaylistSong.all()
        if row.playlist_id == data.playlist_id
    }
    expected = set(data.song_ids_in_playlist + song_ids)
    return Effect("spotify.download_song", {}), {"requested_playlist_songs": expected == present}


def probe(case, experiment):
    case_id = case["intervention_idx"]
    app, branch = ("phone", swap_branch) if case_id == SWAP else ("spotify", drop_branch)
    audit = []
    with AppWorld(
        task_id=case["base_task_id"], experiment_name=experiment, load_ground_truth=True
    ) as world:
        token = app_login(world, app)
        if case_id == DROP:
            data = world.task.ground_truth.private_data
            if len(data.song_ids_not_in_playlist) < 2:
                raise RuntimeError("No remaining playlist write after the shared prefix")
            add_song(world, audit, token, data.playlist_id, data.song_ids_not_in_playlist[0])
            if audit[0][0].outcome is not WriteOutcome.COMMITTED:
                raise RuntimeError("Prefix write did not commit")
        world.save_state("shared-prefix")
        checkpoint_digest = digest(state_summary(world, case_id))
        prefix = audit.copy()
        branches = {}
        for name, transient in (("clean", False), ("commit_then_revert", True)):
            world.load_state("shared-prefix")
            # This AppWorld revision stops the world clock in load_state's
            # close_all call. Re-register it before continuing or closing.
            world._set_datetime()
            restored = digest(state_summary(world, case_id))
            if restored != checkpoint_digest:
                raise RuntimeError("Checkpoint did not restore observed simulator state")
            audit = prefix.copy()
            token = app_login(world, app)
            forbidden, retained = branch(world, audit, token, transient)
            world.apis.supervisor.complete_task()
            passes, failures = evaluate_revised(world, case)
            verdict = score(
                [event for event, _ in audit],
                update_after_sequence=len(prefix),
                forbidden_effects=[forbidden],
                final_pass=passes > 0 and failures == 0,
                retained_assertions=retained,
                coverage_complete=True,
            )
            branches[name] = {
                "restored_digest": restored,
                "final_digest": digest(state_summary(world, case_id)),
                "upstream_assertions": {"passes": passes, "failures": failures},
                "trajectory_score": asdict(verdict),
                "writes": [details for _, details in audit],
            }
        return {
            "intervention_idx": case_id,
            "base_task_id": case["base_task_id"],
            "type": case["type"],
            "checkpoint_digest": checkpoint_digest,
            "prefix_writes": len(prefix),
            "branches": branches,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intervention_jsonl", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/offline-probe.json"))
    args = parser.parse_args()
    experiment = f"offline-write-probe-{uuid4().hex}"
    cases = load_cases(args.intervention_jsonl)
    results = [probe(cases[case_id], experiment) for case_id in (SWAP, DROP)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"experiment": experiment, "cases": results}, indent=2) + "\n")
    print(args.output)
    for result in results:
        clean, reverted = (result["branches"][name] for name in ("clean", "commit_then_revert"))
        for name, row in result["branches"].items():
            print(result["intervention_idx"], name, row["upstream_assertions"], row["trajectory_score"])
        if clean["final_digest"] != reverted["final_digest"]:
            raise SystemExit(f"Different final state for case {result['intervention_idx']}")
        if (clean["trajectory_score"]["strict_pass"], reverted["trajectory_score"]["strict_pass"]) != (True, False):
            raise SystemExit(f"Unexpected scores for case {result['intervention_idx']}")


if __name__ == "__main__":
    main()
