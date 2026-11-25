# Agent skill: order-delivery-analytics

This project's analytics and data-quality layer, packaged as a portable
SKILL.md agent skill (Claude Code, Codex, Cursor).

| Path | What |
|---|---|
| `order-delivery-analytics/` | The skill itself, exactly what goes in the ZIP |
| `tests/test_skill.py` | End-to-end tests: injected defects found exactly, foreign-schema auto-mapping, SQL vs CSV parity, packaging |
| `build_zip.py` | Validates marketplace packaging rules and builds `dist/order-delivery-analytics.zip` |
| `LISTING.md` | Marketplace listing copy (title, description, tags, price) |

```bash
python -m pytest skill/tests -q          # 7 tests, about 20 s
python skill/build_zip.py                # → skill/dist/order-delivery-analytics.zip
```

Try it locally without an agent:

```bash
S=skill/order-delivery-analytics/scripts
python $S/generate_demo_data.py --out /tmp/demo
python $S/dq_audit.py   --mapping /tmp/demo/mapping.json --out /tmp/dq.md
python $S/kpi_report.py --mapping /tmp/demo/mapping.json --out /tmp/kpi.md
```

Install it for Claude Code by copying `order-delivery-analytics/` into
`~/.claude/skills/`.
