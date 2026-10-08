"""Score a frozen run using the external, unchanged AutoWFBench engine."""
import argparse
import hashlib
import os
from pathlib import Path
from autowfbench.runtime.engine import Engine

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('--data-dir', type=Path, default=Path('work/runs'))
    args = parser.parse_args()
    engine = Engine(args.data_dir, os.environ['AWB_JUDGE_URL'], os.environ['AWB_JUDGE_TOKEN'])
    path = engine.directory(args.run_id) / 'run-log.json'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    report = engine.rescore(args.run_id)
    if hashlib.sha256(path.read_bytes()).hexdigest() != before:
        raise RuntimeError('Frozen evidence changed')
    print(f"{args.run_id}: {report['status']} — score={report['score_0_10']}")
    if report['status'] != 'complete':
        raise SystemExit(report.get('judge_error') or 'Judging incomplete')
