# Warp Adapter

Warp is an optional terminal UI. tmux supplies the actual multi-Agent topology
and communication layer.

Start inside a normal Warp shell:

```bash
madw start
```

The attached tmux session already shows:

```text
┌─────────────────────────────────────┐
│ Lead                                │
├──────────────────┬──────────────────┤
│ Impl             │ Review           │
└──────────────────┴──────────────────┘
```

Do not enable Warp synchronized input.

Responsibility boundary:

```text
Warp        = terminal UI
tmux        = panes + addressed transport + synchronization
Lead        = orchestration authority
.agent-team = durable state/evidence
```

No Warp-specific worker Queue is required.
