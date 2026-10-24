# Codex extra-reset forecast

Public experimental probability model and forecast feed. No account data.

The model separates direct resets from banked-card issuance. Current estimates use explicitly disclosed cold-start assumptions, not calibrated historical probabilities. See [MODEL.md](MODEL.md) and [CLIENT_CONTRACT.md](CLIENT_CONTRACT.md).

`model_engine.py` uses Python 3.7+ standard library only, without network, account access or model inference. Public-source collection and the existing two-hour publisher remain separate. Run `python test_engine.py` for regression checks.

`events.json` contains public evidence and revisions. `forecast.json` is the latest checked snapshot; expiry is never renewed after collection failure. `predictions/` preserves dated prospective snapshots for future evaluation, without treating unknown outcomes as failures.
