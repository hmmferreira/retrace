"""Allowlisted PTY protocol: raw exporter output never reaches HTTP or logs."""
import asyncio
import os
import re
import time
from pathlib import Path
import pexpect

PROMPTS = [r"Apple ID: ?", r"Password: ?", r"2FA code: ?",
           r"Choose bottle \[\d+\]: ?", r"Enter the passcode of that device: ?",
           pexpect.EOF, pexpect.TIMEOUT]
KINDS = ["email", "password", "verification_code", "recovery_device", "device_passcode"]
LABELS = {"email": "Apple account email", "password": "Apple account password",
          "verification_code": "SMS verification code", "recovery_device": "Choose a trusted device",
          "device_passcode": "Unlock passcode of the chosen device"}


class ExportFlow:
    def __init__(self, root: Path, executable="/usr/local/bin/findmy-export"):
        self.root, self.executable = root, executable
        self.child = None
        self.owner = None
        self.state = {"phase": "idle"}
        self.deadline = 0
        self.lock = asyncio.Lock()
        self.expiry_task = None
        self._credentials = {}

    def visible(self, owner):
        if self.owner and self.owner != owner:
            return {"phase": "busy", "message": "Another user is completing recovery."}
        return self.state

    async def start(self, owner, credentials=None, fresh_login=False):
        async with self.lock:
            if self.child is not None:
                raise ValueError("Recovery already in progress")
            credentials = credentials or {}
            if credentials and (set(credentials) != {"email", "password"} or any(
                not isinstance(v,str) or not v or len(v)>512 or any(c in v for c in "\r\n\x00")
                for v in credentials.values())):
                raise ValueError("Invalid credentials")
            self._credentials = dict(credentials)
            export = self.root / "export"
            export.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.owner = owner
            self.deadline = time.monotonic() + 600
            self.state = {"phase": "working"}
            try:
                self.child = pexpect.spawn(self.executable,
                    (["--fresh-login"] if fresh_login else []) + ["--anisette-url", "http://127.0.0.1:6969",
                     "--output-dir", str(export / "accessories")],
                    cwd=str(export), encoding="utf-8", echo=False, timeout=90,
                    maxread=4096, searchwindowsize=16384,
                    env={key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR", "XDG_CONFIG_HOME") if key in os.environ})
                self.child.logfile = None
                self.expiry_task = asyncio.create_task(self._expire())
                await self._advance()
            except Exception:
                self._close("failed")
                raise

    async def _expire(self):
        await asyncio.sleep(600)
        async with self.lock:
            self._close("expired")

    async def answer(self, owner, value):
        async with self.lock:
            if owner != self.owner or self.state.get("phase") != "input":
                raise ValueError("No active prompt for this user")
            if time.monotonic() > self.deadline:
                self._close("expired")
                raise ValueError("Recovery expired")
            if not isinstance(value, str) or not value or len(value) > 512 or any(c in value for c in "\r\n\x00"):
                raise ValueError("Invalid response")
            if self.state["kind"] == "recovery_device" and value not in {str(c["value"]) for c in self.state["choices"]}:
                raise ValueError("Choose a listed device")
            # sendline is the PTY's stdin; never argv, environment or a log stream.
            await asyncio.to_thread(self.child.sendline, value)
            self.state = {"phase": "working"}
            await self._advance()

    async def _advance(self):
        child = self.child
        while True:
            index = await asyncio.to_thread(child.expect, PROMPTS)
            kind = KINDS[index] if index < len(KINDS) else None
            value = self._credentials.pop(kind, None)
            if value is None:
                self._credentials.clear()
                break
            await asyncio.to_thread(child.sendline, value)
            value = None
        if index < len(KINDS):
            kind = KINDS[index]
            choices = []
            if kind == "recovery_device":
                for number, label in re.findall(r"\[(\d+)\] [^\r\n]+? \(([^\r\n]+)\)", child.before):
                    choices.append({"value": int(number), "label": label[:100]})
            self.state = {"phase": "input", "kind": kind, "label": LABELS[kind],
                          "secret": kind in ("password", "verification_code", "device_passcode"),
                          "choices": choices}
        elif index == 5:
            child.close()
            self._close("complete" if child.exitstatus == 0 else "failed")
        else:
            self._close("timed_out")

    def _close(self, phase):
        self._credentials.clear()
        if self.child is not None:
            self.child.close(force=True)
            self.child = None
        if self.expiry_task and self.expiry_task is not asyncio.current_task():
            self.expiry_task.cancel()
        self.expiry_task = None
        self.state = {"phase": phase}
        self.owner = None

    async def cancel(self, owner):
        async with self.lock:
            if self.owner and self.owner != owner:
                raise ValueError("Recovery belongs to another user")
            self._close("cancelled")
