from __future__ import annotations

import argparse
import json
from pathlib import Path

from _manifest import (
    EXECUTORS,
    STAGE_ORDER,
    STATUSES,
    VALIDATIONS,
    file_descriptor,
    now,
    read_manifest,
    recompute,
    validate_shape,
    write_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="更新一个研究阶段并记录产物哈希。")
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("stage", choices=STAGE_ORDER)
    parser.add_argument("--status", choices=sorted(STATUSES), required=True)
    parser.add_argument("--executor", choices=sorted(EXECUTORS))
    parser.add_argument("--executor-detail")
    parser.add_argument("--validation", choices=sorted(VALIDATIONS), default="not_run")
    parser.add_argument("--output", action="append", default=[])
    parser.add_argument("--reason")
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    try:
        manifest = read_manifest(run_dir)
        errors = validate_shape(manifest)
        if errors:
            raise ValueError("; ".join(errors))
        outputs = [file_descriptor(run_dir, path) for path in args.output]
        stage = manifest["stages"][args.stage]
        stage.update(
            {
                "status": args.status,
                "executor": args.executor,
                "executor_detail": args.executor_detail,
                "validation": args.validation,
                "outputs": outputs,
                "reason": args.reason,
                "updated_at": now(),
            }
        )
        recompute(manifest)
        write_manifest(run_dir, manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
