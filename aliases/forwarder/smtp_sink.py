#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local-test SMTP sink (MailHog-style): accepts everything on loopback and writes each message to SINK_DIR/<n>.eml."""
import os, time, itertools
from aiosmtpd.controller import Controller
D = os.environ.get("SINK_DIR", "sink"); os.makedirs(D, exist_ok=True); N = itertools.count()
class H:
    async def handle_DATA(self, server, session, env):
        p = os.path.join(D, f"{time.time_ns()}-{next(N)}.eml")
        with open(p, "wb") as f: f.write(f"X-Envelope-From: {env.mail_from}\r\nX-Envelope-To: {','.join(env.rcpt_tos)}\r\n".encode() + env.content)
        return "250 OK"
c = Controller(H(), hostname="127.0.0.1", port=int(os.environ.get("SINK_PORT", "1025"))); c.start()
print(f"smtp-sink 127.0.0.1:{c.port} -> {D}", flush=True)
import threading; threading.Event().wait()
