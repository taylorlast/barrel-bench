# distillery-operator

The model makes every decision; this Harness only manages what it sees.

| `context` | What the model sees each turn |
|---|---|
| `notebook` (default) | System prompt, its own notebook (`notebook_write/read/delete`, capped at `notebook_max_chars`), and the current week's turns. Context resets on every `end_week`. |
| `summary` | Full history until `summarize_at_chars`, then a model-written summary replaces old turns. |
| `window` | The last `window_messages` messages. |

Other config (overridable per Agent via `harness_config`): `briefing` (insert the office
briefing after each week), `max_observation_chars`, `max_idle_replies` (stop after N
replies without tool calls), `max_model_turns`, `temperature`, `max_tokens`.
`model_client: mock` uses `mock_model.py`, a deterministic plumbing exerciser for tests
and offline smoke runs. It is not an evaluated Agent.
