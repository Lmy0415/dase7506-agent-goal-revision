"""Exercise real AppWorld writes and checkpoint restoration without a model."""

from uuid import uuid4

from appworld import AppWorld

from formal_cases import REVOKED, candidates_from
from scoring import Effect, WriteEvent, WriteOutcome, score
from scripts.pilot import DATASET
from scripts.screen_candidates import FormalTools


def probe_arguments(case, world):
    data = world.task.ground_truth.private_data
    public = world.task.ground_truth.public_data
    if case.index == 246:
        return "phone__delete_voice_message", {"voice_message_id": data.to_delete_voice_message_ids[0]}
    if case.index == 260:
        return "gmail__unlabel_thread", {"email_thread_id": data.priority_3_thread_ids[0]}
    if case.index == 386:
        return "phone__update_alarm", {"alarm_id": data.wake_up_alarm_id, "snooze_minutes": public.snooze_minutes}
    if case.index == 390:
        playlist, title = next(iter(data.playlist_id_to_updated_title.items()))
        return "spotify__update_playlist", {"playlist_id": int(playlist), "title": title}
    if case.index == 748:
        send_at = str(data.resignation_datetime).replace("T", "|").replace(" ", "|")[:19]
        return "gmail__update_draft", {"draft_id": data.draft_id, "scheduled_send_at": send_at}
    gmail_user = world.models.gmail.User.find_one(email=world.task.supervisor.email)
    for attachment in world.models.gmail.Attachment.all():
        if attachment.email_id is None:
            continue
        email = world.models.gmail.Email.find_one(id=attachment.email_id)
        if email and gmail_user.id in [email.sender_id, *email.recipient_ids]:
            return "gmail__download_attachment", {
                "attachment_id": attachment.id, "download_to_file_path": f"~/probe-{uuid4().hex}.txt",
            }
    raise RuntimeError("No downloadable attachment was found")


def main():
    for case in candidates_from(DATASET):
        if case.index not in (246, 260, 386, 390, 704, 748):
            continue
        with AppWorld(task_id=case.row["base_task_id"], experiment_name=f"probe-{uuid4().hex}",
                      load_ground_truth=True) as world:
            calls = FormalTools(world, case)
            tool, args = probe_arguments(case, world)
            doc = calls.docs[tool]
            app, api = doc["app_name"], doc["api_name"]
            world.save_state("before-write")
            before = case.signature(world)
            if not calls.is_mutating(doc) or case.write_effect(world, app, api, args) != REVOKED:
                raise RuntimeError(f"{case.index}: intended write was not identified")
            event = calls.run(doc, args, 1)
            if event["status"] != 200 or event["outcome"] != "committed" or event["before"] == event["after"]:
                raise RuntimeError(f"{case.index}: probe did not observe a commit, status {event['status']}")
            world.load_state("before-write")
            world._set_datetime()
            if case.signature(world) != before:
                raise RuntimeError(f"{case.index}: restoring the state did not undo the probe")
            verdict = score(
                [WriteEvent(1, Effect(**event["effect"]), WriteOutcome(event["outcome"]))],
                update_after_sequence=0, forbidden_effects=case.forbidden(), final_pass=True,
                retained_assertions={}, coverage_complete=True,
            )
            if verdict.violation is not True:
                raise RuntimeError(f"{case.index}: commit was lost in trajectory scoring")
            print(case.index, tool, doc["method"], event["status"], event["outcome"], "restored", flush=True)


if __name__ == "__main__":
    main()
