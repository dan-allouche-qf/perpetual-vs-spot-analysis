"""(Re)build the committed Parquet snapshot under data/raw/.

By default this pulls every configured symbol from data.binance.vision (public,
geo-neutral) for the full history window and writes one Parquet file per
(symbol, kind). The snapshot is committed so the notebooks run offline.

Usage:
    python -m scripts.fetch_data                 # all symbols, vision source
    python -m scripts.fetch_data --symbols BTCUSDT
    python -m scripts.fetch_data --source api    # REST fallback (US: HTTP 451)
"""

from __future__ import annotations

import argparse

from perp_spot import config
from perp_spot.data import build_snapshot, build_snapshot_api, save_snapshot


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols", nargs="+", default=list(config.SYMBOLS))
    p.add_argument("--start", default=config.HISTORY_START)
    p.add_argument("--end", default=config.HISTORY_END)
    p.add_argument("--source", choices=("vision", "api"), default="vision")
    args = p.parse_args()

    builder = build_snapshot if args.source == "vision" else build_snapshot_api
    for symbol in args.symbols:
        print(f"[{symbol}] downloading {args.start}..{args.end} from {args.source} ...")
        frames = builder(symbol, args.start, args.end)
        save_snapshot(symbol, frames)
        summary = ", ".join(f"{k}={len(v)}" for k, v in frames.items())
        print(f"[{symbol}] saved snapshot ({summary})")

    print(f"Done. Parquet snapshot written to {config.DATA_DIR}")


if __name__ == "__main__":
    main()
