"""Metered DeepSeek client for the authorized course pilot."""

import argparse
import fcntl
import json
import os
from pathlib import Path

import requests
import truststore
from dotenv import dotenv_values


MODEL = "deepseek-flash"
PILOT_CAP = 1_000_000_000  # nanodollars, US$1
INPUT_PRICE = 300
OUTPUT_PRICE = 1200
ENDPOINT = "https://api.deepseek.com/chat/completions"


class ModelServiceError(RuntimeError):
    pass


class TransientModelError(ModelServiceError):
    pass


class DeepSeekFlash:
    def __init__(self, ledger, *, post=None):
        self.ledger = Path(ledger)
        self.post = post or requests.post
        self.key = (dotenv_values(".env").get("DEEPSEEK_API_KEY") or "").strip()
        if not self.key:
            raise ModelServiceError("DEEPSEEK_API_KEY is missing from the project .env")
        if post is None:
            truststore.inject_into_ssl()

    def request(self, run, messages, *, tools=None, json_mode=False, max_tokens=512):
        payload = {
            "model": MODEL, "messages": messages, "max_tokens": max_tokens,
            "temperature": 0, "thinking": {"type": "disabled"},
        }
        if tools:
            payload["tools"] = tools
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        # Count all request bytes as possible input tokens, with extra room for templates.
        reserve = (len(body) + 4096) * INPUT_PRICE + max_tokens * OUTPUT_PRICE
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a+", encoding="utf-8") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            file.seek(0)
            reservations = {}
            for line in file:
                entry = json.loads(line)
                reservations[entry["id"]] = entry["charge_upper_nanos"]
            if sum(reservations.values()) + reserve > PILOT_CAP:
                raise ModelServiceError("Pilot budget would be exceeded by the next call")
            call_id = len(reservations) + 1
            pending = {"id": call_id, "run": run, "charge_upper_nanos": reserve}
            self._append(file, pending | {"status": "reserved"})
            try:
                response = self.post(
                    ENDPOINT, data=body, timeout=60, allow_redirects=False,
                    headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                )
            except requests.RequestException as error:
                self._append(file, pending | {"status": "transport_error"})
                raise TransientModelError(f"DeepSeek transport error ({type(error).__name__})") from None
            if response.status_code != 200:
                self._append(file, pending | {"status": "http_error", "http": response.status_code})
                error_type = TransientModelError if response.status_code == 429 or response.status_code >= 500 else ModelServiceError
                raise error_type(f"DeepSeek returned HTTP {response.status_code}")
            try:
                data = response.json()
                usage = data["usage"]
                prompt = int(usage["prompt_tokens"])
                completion = int(usage["completion_tokens"])
                choice = data["choices"][0]
            except (ValueError, KeyError, IndexError, TypeError):
                self._append(file, pending | {"status": "unreadable_usage"})
                raise ModelServiceError("DeepSeek response had no usable completion and token record") from None
            upper = prompt * INPUT_PRICE + completion * OUTPUT_PRICE
            self._append(file, pending | {
                "status": "settled", "charge_upper_nanos": upper,
                "prompt_tokens": prompt, "completion_tokens": completion,
                "cache_hit_tokens": usage.get("prompt_cache_hit_tokens"),
                "model": data.get("model"), "fingerprint": data.get("system_fingerprint"),
                "response_id": data.get("id"), "finish_reason": choice.get("finish_reason"),
            })
            if upper > reserve:
                raise ModelServiceError("Reported usage exceeded reservation. Pilot stopped.")
            return choice

    @staticmethod
    def _append(file, entry):
        file.write(json.dumps(entry, separators=(",", ":")) + "\n")
        file.flush()
        os.fsync(file.fileno())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Make one metered DeepSeek Flash smoke-test call.")
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        result = DeepSeekFlash(args.ledger).request(
            "smoke", [{"role": "user", "content": "Reply with OK only."}], max_tokens=12,
        )
    except ModelServiceError as error:
        raise SystemExit(str(error)) from None
    print("DeepSeek smoke check:", (result["message"].get("content") or "").strip() == "OK")
