# Built-in Komboe AI agent

Actionable, metadata-only agent:

- `POST /api/komboe/agent/session`
- `POST /api/komboe/agent/act` with actions: `generate_password`, `security_checklist`, `explain_feature`, `list_unlock_methods`, `local_only_status`

Hard refusal for decrypt/export/master-password actions. Never reads vault plaintext.
