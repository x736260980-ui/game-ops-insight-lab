from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: JSON 顶层必须是对象")
    return value


def extract_video(
    path: Path, source: dict[str, Any], platform: str
) -> list[tuple[str, list[dict[str, Any]]]]:
    """兼容 data.videos、B站 data.posts 和单内容 comments 分片。"""
    if source.get("platform") == platform and isinstance(source.get("data"), dict):
        contents: list[Any] = []
        for field in ("videos", "posts"):
            values = source["data"].get(field) or []
            if not isinstance(values, list):
                raise ValueError(f"{path.name}: data.{field} 必须是数组")
            contents.extend(values)
        result: list[tuple[str, list[dict[str, Any]]]] = []
        for index, content in enumerate(contents, start=1):
            if not isinstance(content, dict):
                raise ValueError(f"{path.name}: 第 {index} 个内容必须是对象")
            comments = ((content.get("comments") or {}).get("items") or [])
            if not isinstance(comments, list):
                raise ValueError(f"{path.name}: 第 {index} 个内容的评论必须是数组")
            content_id = str(
                content.get("video_id")
                or content.get("content_id")
                or content.get("dynamic_id")
                or content.get("note_id")
                or ""
            )
            result.append((content_id, comments))
        return result

    video = source.get("video")
    comments = source.get("comments")
    if isinstance(video, dict) and isinstance(comments, list):
        if video.get("platform") not in (None, platform):
            raise ValueError(
                f"{path.name}: video.platform={video.get('platform')!r}，不是 {platform} 数据"
            )
        return [(str(video.get("video_id") or ""), comments)]
    raise ValueError(f"{path.name}: 无法识别为 {platform} 采集结果或评论分片")


def build_output(
    sources: list[tuple[str, list[dict[str, Any]]]],
    target: str | None,
    platform: str,
    prefix: str,
) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    video_ids: list[str] = []
    for video_id, comments in sources:
        if video_id and video_id not in video_ids:
            video_ids.append(video_id)
        for comment in comments:
            if not isinstance(comment, dict):
                raise ValueError("评论必须是对象")
            comment_id = str(comment.get("comment_id") or "")
            content = comment.get("content")
            if content is None:
                content = ""
            if not isinstance(content, str):
                raise ValueError("评论正文必须是字符串")
            key = ("id", comment_id) if comment_id else (("content", content) if content else None)
            if key is not None and key in seen:
                continue
            if key is not None:
                seen.add(key)
            merged.append({**comment, "content": content})

    numbered: dict[str, dict[str, Any]] = {}
    for index, comment in enumerate(merged, start=1):
        numbered[f"{prefix}{index:04d}"] = {
            "text": comment["content"],
            "relevance_score": None,
            "relevance_label": None,
        }
    return {
        "schema_version": "relevance-input-1.0",
        "platform": platform,
        "video_ids": video_ids,
        "relevance_target": target,
        "comments": numbered,
    }


def run_cli(
    platform: str,
    prefix: str,
    default_input: Path,
    default_output: Path,
) -> None:
    parser = argparse.ArgumentParser(
        description=f"把 {platform} 多视频采集结果或原始分片转换为 relevance-input-1.0。"
    )
    parser.add_argument("--input", type=Path, nargs="+", default=[], help="输入 JSON，可传多个")
    parser.add_argument("--input-dir", type=Path, default=None, help="读取目录下所有 *.json")
    parser.add_argument("--output", type=Path, default=default_output, help="输出 JSON")
    parser.add_argument("--target", default=None, help="相关性判断目标")
    args = parser.parse_args()

    files: list[Path] = []
    if args.input_dir is not None:
        files.extend(sorted(args.input_dir.glob("*.json")))
    files.extend(args.input)
    if not files and default_input.exists():
        files.append(default_input)
    if not files:
        raise SystemExit("未指定输入：请用 --input 或 --input-dir 指定输入")

    sources: list[tuple[str, list[dict[str, Any]]]] = []
    for path in files:
        sources.extend(extract_video(path, load_json(path), platform))
    result = build_output(sources, args.target, platform, prefix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        f"已生成 {args.output}：评论数 {len(result['comments'])}"
        f"（视频 {len(result['video_ids'])} 个: {result['video_ids']}）"
    )
