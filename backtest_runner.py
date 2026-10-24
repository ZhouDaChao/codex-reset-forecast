"""Offline walk-forward diagnostic. Never writes the production feed."""
import argparse
import json
from pathlib import Path
from model_engine import time, backtest, atomic_json

if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger",default="events.json")
    p.add_argument("--params",default="parameters.json")
    p.add_argument("--cutoffs",nargs="+",required=True)
    p.add_argument("--evaluation-time",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    ledger=json.loads(Path(a.ledger).read_text(encoding="utf-8"))
    params=json.loads(Path(a.params).read_text(encoding="utf-8"))
    atomic_json(a.output,backtest(ledger,params,[time(x) for x in a.cutoffs],time(a.evaluation_time)))
