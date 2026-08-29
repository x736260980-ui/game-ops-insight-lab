from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable


INPUT_SCHEMA = "game-comment-insight-input-1.0"
PLAN_SCHEMA = "game-comment-classification-plan-1.0"
SEMANTIC_SCHEMA = "game-comment-semantic-analysis-1.0"
DASHBOARD_SCHEMA = "game-comment-dashboard-1.1"
LEGACY_DASHBOARD_SCHEMA = "game-comment-dashboard-1.0"
AUDIT_SCHEMA = "game-comment-analysis-audit-1.0"
WEB_BACKGROUND_SCHEMA = "web-background-1.0"
WEB_ENRICHMENT_SCHEMA = "web-enrichment-1.0"
SENTIMENTS = ("positive", "negative", "neutral", "mixed")
CATEGORY_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{1,63}")
WEB_ID_PATTERN = re.compile(r"WEB-[0-9]{3,}")
FENCED_JSON_PATTERN = re.compile(
    r"\A\s*```(?:json)?\s*\r?\n(?P<body>.*?)\r?\n```\s*\Z",
    re.IGNORECASE | re.DOTALL,
)


class DashboardError(ValueError):
    """输入契约不满足时停止流程。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DashboardError(message)


def parse_json_document(text: str) -> Any:
    require(isinstance(text, str), "输入必须是 JSON 文本")
    stripped = text.strip()
    match = FENCED_JSON_PATTERN.fullmatch(stripped)
    if match:
        stripped = match.group("body").strip()
    elif "```" in stripped:
        raise DashboardError("只接受纯 JSON 或被完整 JSON 代码块包裹的完整 JSON")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise DashboardError(
            f"JSON 解析失败（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}"
        ) from exc


def load_json_file(path: Path | str) -> Any:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise DashboardError(f"无法读取文件：{file_path}（{exc}）") from exc
    return parse_json_document(text)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _positive_int(value: Any, label: str) -> int:
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{label} 必须是正整数")
    return value


def _empty_web_context(status: str = "not_provided") -> dict[str, Any]:
    return {
        "status": status,
        "candidate_count": 0,
        "used_source_count": 0,
        "event_background": [],
        "corroborations": [],
        "counter_signals": [],
        "sources": [],
        "source_limitations": [],
    }


def _normalize_comment_collection(
    document: Any, source: str
) -> tuple[str, list[dict[str, Any]]]:
    require(isinstance(document, dict), f"{source} 顶层必须是对象")
    platform = document.get("platform")
    require(isinstance(platform, str) and platform.strip(),
            f"{source}.platform 必须是非空字符串")
    platform = platform.strip().lower()
    raw_comments = document.get("comments")
    require(isinstance(raw_comments, (list, dict)),
            f"{source}.comments 必须是数组或编号映射对象")

    comments: list[dict[str, Any]] = []
    if isinstance(raw_comments, list):
        iterable: Iterable[tuple[Any, Any]] = enumerate(raw_comments)
    else:
        iterable = raw_comments.items()

    seen: set[str] = set()
    for key, raw in iterable:
        label = f"{source}.comments[{key}]"
        if isinstance(raw_comments, list):
            require(isinstance(raw, dict), f"{label} 必须是对象")
            record_id = raw.get("record_id")
            item = dict(raw)
        else:
            record_id = key
            if isinstance(raw, str):
                item = {"text": raw}
            else:
                require(isinstance(raw, dict), f"{label} 必须是字符串或对象")
                item = dict(raw)
                embedded_id = item.get("record_id")
                require(embedded_id in (None, record_id),
                        f"{label} 的键与 record_id 不一致")
        require(isinstance(record_id, str) and record_id.strip(),
                f"{label}.record_id 必须是非空字符串")
        record_id = record_id.strip()
        require(record_id not in seen, f"{source} 存在重复编号：{record_id}")
        seen.add(record_id)
        text = item.get("text")
        require(isinstance(text, str), f"{record_id}.text 必须是字符串")
        comments.append({"record_id": record_id, "text": text, **item})
        comments[-1]["record_id"] = record_id
        comments[-1]["text"] = text
    return platform, comments


def _load_relevance(
    relevance_paths: Iterable[Path | str],
) -> tuple[list[str], dict[str, OrderedDict[str, str]]]:
    platform_order: list[str] = []
    by_platform: dict[str, OrderedDict[str, str]] = {}
    global_ids: dict[str, str] = {}
    paths = list(relevance_paths)
    require(paths, "至少需要一个相关性结果文件")
    for path in paths:
        platform, comments = _normalize_comment_collection(
            load_json_file(path), f"相关性文件 {path}"
        )
        if platform not in by_platform:
            platform_order.append(platform)
            by_platform[platform] = OrderedDict()
        for item in comments:
            record_id = item["record_id"]
            require(record_id not in global_ids,
                    f"相关性结果存在重复编号：{record_id}")
            global_ids[record_id] = platform
            by_platform[platform][record_id] = item["text"]
    return platform_order, by_platform


def _load_cluster_indexes(
    index_paths: Iterable[Path | str],
) -> dict[str, dict[str, list[str]]]:
    result: dict[str, dict[str, list[str]]] = {}
    for path in index_paths:
        document = load_json_file(path)
        require(isinstance(document, dict), f"聚类索引 {path} 顶层必须是对象")
        platform = document.get("platform")
        require(isinstance(platform, str) and platform.strip(),
                f"聚类索引 {path}.platform 必须是非空字符串")
        platform = platform.strip().lower()
        clusters = document.get("clusters")
        require(isinstance(clusters, (list, dict)),
                f"聚类索引 {path}.clusters 必须是数组或对象")
        values = clusters if isinstance(clusters, list) else clusters.values()
        platform_map = result.setdefault(platform, {})
        for index, raw in enumerate(values):
            require(isinstance(raw, dict), f"聚类索引 {path} 第 {index + 1} 项必须是对象")
            representative_id = raw.get("representative_id")
            member_ids = raw.get("member_ids")
            require(isinstance(representative_id, str) and representative_id,
                    f"聚类索引 {path} 第 {index + 1} 项 representative_id 非法")
            require(isinstance(member_ids, list) and len(member_ids) >= 2
                    and all(isinstance(x, str) and x for x in member_ids),
                    f"聚类索引 {path} 中 {representative_id}.member_ids 非法")
            require(len(member_ids) == len(set(member_ids)),
                    f"聚类索引 {path} 中 {representative_id} 的成员重复")
            require(representative_id in member_ids,
                    f"聚类索引 {path} 中 {representative_id} 必须属于成员")
            if "support_count" in raw:
                support = _positive_int(raw["support_count"],
                                        f"聚类索引 {representative_id}.support_count")
                require(support == len(member_ids),
                        f"聚类索引 {representative_id}.support_count 与成员数量不一致")
            require(representative_id not in platform_map,
                    f"聚类索引存在重复代表编号：{representative_id}")
            platform_map[representative_id] = list(member_ids)
    return result


def prepare_analysis_input(
    research_target: str,
    relevance_paths: Iterable[Path | str],
    folded_paths: Iterable[Path | str],
    cluster_index_paths: Iterable[Path | str] = (),
) -> dict[str, Any]:
    require(isinstance(research_target, str) and research_target.strip(),
            "research_target 必须是非空字符串")
    platform_order, relevance = _load_relevance(relevance_paths)
    indexes = _load_cluster_indexes(cluster_index_paths)
    paths = list(folded_paths)
    require(paths, "至少需要一个折叠结果文件")

    folded_by_platform: dict[str, list[dict[str, Any]]] = {
        platform: [] for platform in platform_order
    }
    seen_representatives: set[str] = set()
    represented_members: dict[str, str] = {}
    for path in paths:
        platform, comments = _normalize_comment_collection(
            load_json_file(path), f"折叠文件 {path}"
        )
        require(platform in relevance, f"折叠文件包含未知平台：{platform}")
        text_by_id = relevance[platform]
        for item in comments:
            record_id = item["record_id"]
            require(record_id not in seen_representatives,
                    f"折叠结果存在重复代表编号：{record_id}")
            seen_representatives.add(record_id)
            require(record_id in text_by_id, f"折叠结果包含未知编号：{record_id}")
            require(item["text"] == text_by_id[record_id],
                    f"折叠结果修改了 {record_id} 的原文")

            members = item.get("merged_record_ids")
            indexed_members = indexes.get(platform, {}).get(record_id)
            if members is None:
                members = indexed_members or [record_id]
            require(isinstance(members, list) and members
                    and all(isinstance(x, str) and x for x in members),
                    f"{record_id}.merged_record_ids 必须是非空字符串数组")
            require(len(members) == len(set(members)),
                    f"{record_id}.merged_record_ids 存在重复成员")
            require(record_id in members,
                    f"{record_id} 必须属于自己的 merged_record_ids")
            if indexed_members is not None:
                require(members == indexed_members,
                        f"{record_id} 与 cluster-index 的成员不一致")

            support = item.get("support_count", len(members))
            support = _positive_int(support, f"{record_id}.support_count")
            require(support == len(members),
                    f"{record_id}.support_count 与 merged_record_ids 数量不一致")
            for member_id in members:
                require(member_id in text_by_id,
                        f"折叠结果包含未知成员编号：{member_id}")
                require(member_id not in represented_members,
                        f"折叠结果重复表示成员编号：{member_id}")
                represented_members[member_id] = record_id
            folded_by_platform[platform].append({
                "record_id": record_id,
                "platform": platform,
                "text": item["text"],
                "support_count": support,
                "merged_record_ids": list(members),
            })

    all_relevance_ids = {
        record_id for comments in relevance.values() for record_id in comments
    }
    missing = sorted(all_relevance_ids - set(represented_members))
    require(not missing,
            "折叠结果缺失相关性保留编号：" + ", ".join(missing[:20]))
    extra_index_reps = sorted(
        rep
        for platform, reps in indexes.items()
        for rep in reps
        if rep not in seen_representatives
    )
    require(not extra_index_reps,
            "cluster-index 包含未出现在折叠结果中的代表编号："
            + ", ".join(extra_index_reps[:20]))

    platforms: list[dict[str, Any]] = []
    normalized_comments: list[dict[str, Any]] = []
    for platform in platform_order:
        folded = folded_by_platform[platform]
        relevance_count = len(relevance[platform])
        represented_count = sum(item["support_count"] for item in folded)
        require(represented_count == relevance_count,
                f"{platform} 折叠数量对账失败：相关性 {relevance_count}，代表 {represented_count}")
        platforms.append({
            "platform": platform,
            "relevance_count": relevance_count,
            "folded_count": len(folded),
            "represented_count": represented_count,
        })
        normalized_comments.extend(folded)

    return {
        "schema_version": INPUT_SCHEMA,
        "research_target": research_target.strip(),
        "platforms": platforms,
        "comments": normalized_comments,
    }


def prepare_analysis_input_from_folded(
    research_target: str,
    folded_paths: Iterable[Path | str],
) -> dict[str, Any]:
    """生成三文件交接模式下的统一分析输入。

    该模式只能核对折叠文件内部的代表编号、成员编号和数量，无法核验未作为
    代表的评论原文，因为Dify没有同时交付折叠前的相关性全集。
    """
    require(isinstance(research_target, str) and research_target.strip(),
            "research_target 必须是非空字符串")
    paths = list(folded_paths)
    require(paths, "至少需要一个折叠结果文件")

    platform_order: list[str] = []
    platform_counts: dict[str, dict[str, int]] = {}
    normalized_comments: list[dict[str, Any]] = []
    seen_record_ids: set[str] = set()
    represented_members: dict[str, str] = {}

    for path in paths:
        platform, comments = _normalize_comment_collection(
            load_json_file(path), f"折叠文件 {path}"
        )
        if platform not in platform_counts:
            platform_order.append(platform)
            platform_counts[platform] = {
                "folded_count": 0,
                "represented_count": 0,
            }

        for item in comments:
            record_id = item["record_id"]
            require(record_id not in seen_record_ids,
                    f"折叠结果存在重复编号：{record_id}")
            seen_record_ids.add(record_id)

            members = item.get("merged_record_ids", [record_id])
            require(isinstance(members, list) and members
                    and all(isinstance(value, str) and value for value in members),
                    f"{record_id}.merged_record_ids 必须是非空字符串数组")
            require(len(members) == len(set(members)),
                    f"{record_id}.merged_record_ids 存在重复成员")
            require(record_id in members,
                    f"{record_id} 必须属于自己的 merged_record_ids")

            support_count = _positive_int(
                item.get("support_count", len(members)),
                f"{record_id}.support_count",
            )
            require(support_count == len(members),
                    f"{record_id}.support_count 与 merged_record_ids 数量不一致")
            for member_id in members:
                require(member_id not in represented_members,
                        f"折叠结果重复表示成员编号：{member_id}")
                represented_members[member_id] = record_id

            normalized_comments.append({
                "record_id": record_id,
                "platform": platform,
                "text": item["text"],
                "support_count": support_count,
                "merged_record_ids": list(members),
            })
            platform_counts[platform]["folded_count"] += 1
            platform_counts[platform]["represented_count"] += support_count

    platforms = []
    for platform in platform_order:
        counts = platform_counts[platform]
        platforms.append({
            "platform": platform,
            "relevance_count": counts["represented_count"],
            "folded_count": counts["folded_count"],
            "represented_count": counts["represented_count"],
        })

    return {
        "schema_version": INPUT_SCHEMA,
        "research_target": research_target.strip(),
        "platforms": platforms,
        "comments": normalized_comments,
    }


def validate_taxonomy(plan: Any, require_approved: bool = False) -> dict[str, Any]:
    require(isinstance(plan, dict), "classification-plan 顶层必须是对象")
    require(plan.get("schema_version") == PLAN_SCHEMA,
            f"classification-plan.schema_version 必须是 {PLAN_SCHEMA}")
    target = plan.get("research_target")
    require(isinstance(target, str) and target.strip(),
            "classification-plan.research_target 必须是非空字符串")
    status = plan.get("status")
    require(status in {"draft", "approved"},
            "classification-plan.status 必须是 draft 或 approved")
    if require_approved:
        require(status == "approved", "分类表 status 必须设为 approved 后才能继续")
    plan_version = plan.get("plan_version")
    require(isinstance(plan_version, str) and plan_version.strip(),
            "classification-plan.plan_version 必须是稳定的非空版本号")
    categories = plan.get("categories")
    require(isinstance(categories, list), "classification-plan.categories 必须是数组")

    seen: set[str] = set()
    other_count = 0
    for index, category in enumerate(categories):
        label = f"categories[{index}]"
        require(isinstance(category, dict), f"{label} 必须是对象")
        category_id = category.get("category_id")
        require(isinstance(category_id, str)
                and CATEGORY_ID_PATTERN.fullmatch(category_id) is not None,
                f"{label}.category_id 必须是稳定的小写英文或下划线 ID")
        require(category_id not in seen, f"分类 ID 重复：{category_id}")
        seen.add(category_id)
        other_count += int(category_id == "other")
        for field in ("name", "definition"):
            value = category.get(field)
            require(isinstance(value, str) and value.strip(),
                    f"{label}.{field} 必须是非空字符串")
        for field in ("include_if", "exclude_if"):
            value = category.get(field)
            require(isinstance(value, list) and value
                    and all(isinstance(x, str) and x.strip() for x in value),
                    f"{label}.{field} 必须是非空字符串数组")
    require(other_count == 1, "分类表必须且只能包含一个 other 兜底类别")
    dynamic_count = len(categories) - 1
    require(4 <= dynamic_count <= 8, "分类表必须包含 4—8 个动态类别，另加 other")
    return plan


def _validate_analysis_input(value: Any) -> dict[str, Any]:
    require(isinstance(value, dict), "analysis-input 顶层必须是对象")
    require(value.get("schema_version") == INPUT_SCHEMA,
            f"analysis-input.schema_version 必须是 {INPUT_SCHEMA}")
    target = value.get("research_target")
    require(isinstance(target, str) and target.strip(),
            "analysis-input.research_target 必须是非空字符串")
    platforms = value.get("platforms")
    comments = value.get("comments")
    require(isinstance(platforms, list) and platforms, "analysis-input.platforms 必须是非空数组")
    require(isinstance(comments, list), "analysis-input.comments 必须是数组")

    platform_by_id: dict[str, dict[str, int]] = {}
    for index, raw in enumerate(platforms):
        require(isinstance(raw, dict), f"platforms[{index}] 必须是对象")
        platform = raw.get("platform")
        require(isinstance(platform, str) and platform and platform not in platform_by_id,
                f"platforms[{index}].platform 非法或重复")
        normalized: dict[str, int] = {}
        for field in ("relevance_count", "folded_count", "represented_count"):
            number = raw.get(field)
            require(isinstance(number, int) and not isinstance(number, bool) and number >= 0,
                    f"{platform}.{field} 必须是非负整数")
            normalized[field] = number
        require(normalized["relevance_count"] == normalized["represented_count"],
                f"{platform} relevance_count 与 represented_count 不一致")
        platform_by_id[platform] = normalized

    seen_ids: set[str] = set()
    seen_members: set[str] = set()
    calculated: dict[str, dict[str, int]] = {
        platform: {"folded_count": 0, "represented_count": 0}
        for platform in platform_by_id
    }
    for index, item in enumerate(comments):
        label = f"comments[{index}]"
        require(isinstance(item, dict), f"{label} 必须是对象")
        record_id = item.get("record_id")
        platform = item.get("platform")
        text = item.get("text")
        require(isinstance(record_id, str) and record_id,
                f"{label}.record_id 必须是非空字符串")
        require(record_id not in seen_ids, f"analysis-input 存在重复编号：{record_id}")
        seen_ids.add(record_id)
        require(platform in platform_by_id, f"{record_id} 包含未知平台：{platform}")
        require(isinstance(text, str), f"{record_id}.text 必须是字符串")
        support = _positive_int(item.get("support_count"), f"{record_id}.support_count")
        members = item.get("merged_record_ids")
        require(isinstance(members, list) and len(members) == support
                and all(isinstance(x, str) and x for x in members),
                f"{record_id}.merged_record_ids 必须与 support_count 完整对应")
        require(len(members) == len(set(members)), f"{record_id} 的折叠成员重复")
        require(record_id in members, f"{record_id} 必须属于自己的折叠成员")
        overlap = set(members) & seen_members
        require(not overlap, "analysis-input 折叠成员重复：" + ", ".join(sorted(overlap)))
        seen_members.update(members)
        calculated[platform]["folded_count"] += 1
        calculated[platform]["represented_count"] += support
    for platform, expected in platform_by_id.items():
        require(calculated[platform] == {
                    "folded_count": expected["folded_count"],
                    "represented_count": expected["represented_count"],
                }, f"{platform} 的 analysis-input 数量对账失败")
    return value


def _ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _empty_sentiment_counts() -> dict[str, int]:
    return {sentiment: 0 for sentiment in SENTIMENTS}


def _sentiment_output(counts: dict[str, int], total: int) -> dict[str, dict[str, Any]]:
    return {
        sentiment: {"count": counts[sentiment], "ratio": _ratio(counts[sentiment], total)}
        for sentiment in SENTIMENTS
    }


def _fingerprint(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def finalize_dashboard(
    analysis_input: Any, classification_plan: Any, semantic_analysis: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = _validate_analysis_input(analysis_input)
    plan = validate_taxonomy(classification_plan, require_approved=True)
    require(plan["research_target"].strip() == source["research_target"].strip(),
            "classification-plan 与 analysis-input 的研究主题不一致")
    require(isinstance(semantic_analysis, dict), "semantic-analysis 顶层必须是对象")
    schema = semantic_analysis.get("schema_version")
    require(schema in (None, SEMANTIC_SCHEMA),
            f"semantic-analysis.schema_version 必须是 {SEMANTIC_SCHEMA}")
    semantic_target = semantic_analysis.get("research_target")
    require(semantic_target in (None, source["research_target"]),
            "semantic-analysis 与 analysis-input 的研究主题不一致")

    comments = {item["record_id"]: item for item in source["comments"]}
    category_defs = {item["category_id"]: item for item in plan["categories"]}
    results = semantic_analysis.get("results")
    require(isinstance(results, list), "semantic-analysis.results 必须是数组")
    result_by_id: dict[str, dict[str, Any]] = {}
    included_by_category: dict[str, list[str]] = {key: [] for key in category_defs}
    secondary_exclusions: list[dict[str, Any]] = []
    overall_counts = _empty_sentiment_counts()
    category_counts: dict[str, int] = {key: 0 for key in category_defs}
    category_sentiments: dict[str, dict[str, int]] = {
        key: _empty_sentiment_counts() for key in category_defs
    }
    platform_included: dict[str, dict[str, int]] = {
        item["platform"]: {"folded": 0, "represented": 0, "excluded": 0}
        for item in source["platforms"]
    }

    for index, raw in enumerate(results):
        require(isinstance(raw, dict), f"results[{index}] 必须是对象")
        record_id = raw.get("record_id")
        require(isinstance(record_id, str) and record_id, f"results[{index}].record_id 非法")
        require(record_id not in result_by_id, f"semantic-analysis 存在重复编号：{record_id}")
        require(record_id in comments, f"semantic-analysis 包含未知编号：{record_id}")
        result_by_id[record_id] = raw
        comment = comments[record_id]
        support = comment["support_count"]
        include = raw.get("include_in_dashboard")
        require(isinstance(include, bool), f"{record_id}.include_in_dashboard 必须是布尔值")
        aspects = raw.get("aspects")
        require(isinstance(aspects, list), f"{record_id}.aspects 必须是数组")
        if not include:
            reason = raw.get("exclusion_reason")
            require(isinstance(reason, str) and reason.strip(),
                    f"{record_id} 二次排除时必须提供 exclusion_reason")
            require(raw.get("overall_sentiment") is None and not aspects,
                    f"{record_id} 被二次排除后不得保留情绪或类别")
            platform_included[comment["platform"]]["excluded"] += support
            secondary_exclusions.append({
                "record_id": record_id,
                "platform": comment["platform"],
                "support_count": support,
                "merged_record_ids": list(comment["merged_record_ids"]),
                "reason": reason.strip(),
            })
            continue

        overall = raw.get("overall_sentiment")
        require(overall in SENTIMENTS, f"{record_id}.overall_sentiment 非法")
        require(aspects, f"{record_id} 纳入看板时至少需要一个类别")
        seen_categories: set[str] = set()
        for aspect_index, aspect in enumerate(aspects):
            require(isinstance(aspect, dict),
                    f"{record_id}.aspects[{aspect_index}] 必须是对象")
            category_id = aspect.get("category_id")
            sentiment = aspect.get("sentiment")
            require(category_id in category_defs,
                    f"{record_id} 使用未知类别：{category_id}")
            require(category_id not in seen_categories,
                    f"{record_id} 存在重复类别：{category_id}")
            seen_categories.add(category_id)
            require(sentiment in SENTIMENTS,
                    f"{record_id} 在 {category_id} 下的 sentiment 非法")
            included_by_category[category_id].append(record_id)
            category_counts[category_id] += support
            category_sentiments[category_id][sentiment] += support
        require(not ("other" in seen_categories and len(seen_categories) > 1),
                f"{record_id} 的 other 不能与具体类别同时使用")
        overall_counts[overall] += support
        platform_included[comment["platform"]]["folded"] += 1
        platform_included[comment["platform"]]["represented"] += support

    extra_ids = sorted(set(result_by_id) - set(comments))
    missing_ids = sorted(set(comments) - set(result_by_id))
    require(not extra_ids, "semantic-analysis 包含多余编号：" + ", ".join(extra_ids))
    require(not missing_ids, "semantic-analysis 缺失编号：" + ", ".join(missing_ids))

    outputs = semantic_analysis.get("category_outputs")
    require(isinstance(outputs, list), "semantic-analysis.category_outputs 必须是数组")
    output_by_category: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(outputs):
        require(isinstance(raw, dict), f"category_outputs[{index}] 必须是对象")
        category_id = raw.get("category_id")
        require(category_id in category_defs,
                f"category_outputs 使用未知类别：{category_id}")
        require(category_id not in output_by_category,
                f"category_outputs 类别重复：{category_id}")
        summary = raw.get("summary")
        representative_ids = raw.get("representative_ids")
        require(isinstance(summary, str) and summary.strip(),
                f"{category_id}.summary 必须是非空字符串")
        require(isinstance(representative_ids, list)
                and all(isinstance(x, str) and x for x in representative_ids),
                f"{category_id}.representative_ids 必须是字符串数组")
        require(len(representative_ids) <= 2,
                f"{category_id} 最多两条代表评论")
        require(len(representative_ids) == len(set(representative_ids)),
                f"{category_id}.representative_ids 存在重复编号")
        for record_id in representative_ids:
            require(record_id in comments, f"{category_id} 代表评论包含未知编号：{record_id}")
            require(record_id in included_by_category[category_id],
                    f"代表评论 {record_id} 不属于类别 {category_id}")
        output_by_category[category_id] = raw

    used_categories = {key for key, ids in included_by_category.items() if ids}
    missing_outputs = sorted(used_categories - set(output_by_category))
    unused_outputs = sorted(set(output_by_category) - used_categories)
    require(not missing_outputs,
            "有评论的类别缺失 category_outputs：" + ", ".join(missing_outputs))
    require(not unused_outputs,
            "category_outputs 包含没有评论的类别：" + ", ".join(unused_outputs))

    input_total = sum(item["relevance_count"] for item in source["platforms"])
    represented_total = sum(item["represented_count"] for item in source["platforms"])
    folded_total = len(source["comments"])
    excluded_total = sum(item["support_count"] for item in secondary_exclusions)
    final_total = sum(overall_counts.values())
    require(input_total == represented_total,
            "相关性输入数量与折叠代表数量无法对账")
    require(excluded_total + final_total == represented_total,
            "总体情绪数量与最终评论总量无法对账")

    platform_output: list[dict[str, Any]] = []
    for item in source["platforms"]:
        platform = item["platform"]
        included = platform_included[platform]
        require(included["represented"] + included["excluded"] == item["represented_count"],
                f"{platform} 的纳入与排除数量无法对账")
        platform_output.append({
            **item,
            "included_folded_count": included["folded"],
            "included_represented_count": included["represented"],
            "secondary_excluded_count": included["excluded"],
        })

    category_output: list[dict[str, Any]] = []
    for category in plan["categories"]:
        category_id = category["category_id"]
        if category_id not in used_categories:
            continue
        count = category_counts[category_id]
        sentiment = category_sentiments[category_id]
        require(sum(sentiment.values()) == count,
                f"类别 {category_id} 的情绪数量与类别加权数量不一致")
        generated = output_by_category[category_id]
        representatives = []
        for record_id in generated["representative_ids"]:
            comment = comments[record_id]
            representatives.append({
                "record_id": record_id,
                "platform": comment["platform"],
                "text": comment["text"],
                "support_count": comment["support_count"],
            })
        category_output.append({
            "category_id": category_id,
            "name": category["name"],
            "count": count,
            "ratio_of_final_analyzed": _ratio(count, final_total),
            "sentiment": _sentiment_output(sentiment, count),
            "summary": generated["summary"].strip(),
            "representative_comments": representatives,
        })

    dashboard = {
        "schema_version": DASHBOARD_SCHEMA,
        "research_target": source["research_target"],
        "counts": {
            "input_relevance_count": input_total,
            "folded_record_count": folded_total,
            "represented_comment_count": represented_total,
            "secondary_excluded_count": excluded_total,
            "final_analyzed_count": final_total,
        },
        "platforms": platform_output,
        "overall_sentiment": _sentiment_output(overall_counts, final_total),
        "category_statistics_non_exclusive": True,
        "categories": category_output,
        "web_context": _empty_web_context(),
        "methodology": {
            "weighting": "所有数量按 support_count 加权；同质折叠的代表评论代表其全部成员。",
            "category_scope": "类别为多选且互不排斥，类别数量与占比之和可以超过最终评论量或 100%。",
            "overall_sentiment_scope": "每个折叠代表记录只进行一次总体情绪判断；统计时按 support_count 计入其代表的全部评论。",
            "limitations": [
                "公开平台评论是有偏样本，不代表全体玩家。",
                "Python只校验编号、原文和数量，不重新判断Dify折叠的语义正确性。",
                "网页资料如有仅在独立 web_context 中展示",
            ],
        },
    }
    audit = {
        "schema_version": AUDIT_SCHEMA,
        "research_target": source["research_target"],
        "classification_plan": {
            "plan_version": plan["plan_version"],
            "status": plan["status"],
            "category_ids": [item["category_id"] for item in plan["categories"]],
            "sha256": _fingerprint(plan),
        },
        "secondary_exclusions": secondary_exclusions,
        "validation": {
            "missing_result_ids": [],
            "extra_result_ids": [],
            "duplicate_result_ids": [],
        },
        "fold_reconciliation": {
            "relevance_count": input_total,
            "folded_record_count": folded_total,
            "represented_count": represented_total,
            "unique_merged_record_id_count": len({
                member
                for item in source["comments"]
                for member in item["merged_record_ids"]
            }),
            "platforms": source["platforms"],
        },
        "semantic_result_count": len(result_by_id),
    }
    return dashboard, audit


def _required_text(value: Any, label: str) -> str:
    require(isinstance(value, str) and value.strip(), f"{label} 必须是非空字符串")
    return value.strip()


def _source_refs(value: Any, label: str, known_ids: set[str]) -> list[str]:
    require(isinstance(value, list) and value, f"{label} 必须是非空数组")
    refs: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        ref = _required_text(raw, f"{label}[{index}]")
        require(ref not in seen, f"{label} 存在重复来源编号：{ref}")
        require(ref in known_ids, f"{label} 引用了不存在的网页来源：{ref}")
        seen.add(ref)
        refs.append(ref)
    return refs


def merge_web_context(
    dashboard: Any, web_background: Any, web_enrichment: Any
) -> dict[str, Any]:
    require(isinstance(dashboard, dict), "dashboard 顶层必须是对象")
    require(
        dashboard.get("schema_version") in {LEGACY_DASHBOARD_SCHEMA, DASHBOARD_SCHEMA},
        f"dashboard.schema_version 必须是 {LEGACY_DASHBOARD_SCHEMA} 或 {DASHBOARD_SCHEMA}",
    )
    target = _required_text(dashboard.get("research_target"), "dashboard.research_target")
    raw_categories = dashboard.get("categories")
    require(isinstance(raw_categories, list), "dashboard.categories 必须是数组")
    category_ids: set[str] = set()
    for index, category in enumerate(raw_categories):
        require(isinstance(category, dict), f"dashboard.categories[{index}] 必须是对象")
        category_id = _required_text(
            category.get("category_id"), f"dashboard.categories[{index}].category_id"
        )
        require(category_id not in category_ids, f"dashboard 存在重复类别：{category_id}")
        category_ids.add(category_id)

    require(isinstance(web_background, dict), "web-background 顶层必须是对象")
    require(
        web_background.get("schema_version") == WEB_BACKGROUND_SCHEMA,
        f"web-background.schema_version 必须是 {WEB_BACKGROUND_SCHEMA}",
    )
    background_target = _required_text(
        web_background.get("research_target"), "web-background.research_target"
    )
    require(background_target == target, "web-background 与 dashboard 的研究主题不一致")
    raw_results = web_background.get("results")
    require(isinstance(raw_results, list), "web-background.results 必须是数组")

    source_by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for index, raw in enumerate(raw_results):
        label = f"web-background.results[{index}]"
        require(isinstance(raw, dict), f"{label} 必须是对象")
        web_id = _required_text(raw.get("web_id"), f"{label}.web_id")
        require(WEB_ID_PATTERN.fullmatch(web_id) is not None, f"{label}.web_id 格式非法：{web_id}")
        require(web_id not in source_by_id, f"web-background 存在重复来源编号：{web_id}")
        url = _required_text(raw.get("url"), f"{label}.url")
        require(re.fullmatch(r"https?://\S+", url) is not None, f"{label}.url 必须是 HTTP(S) URL")
        published_at = raw.get("published_at")
        require(
            published_at is None or (isinstance(published_at, str) and published_at.strip()),
            f"{label}.published_at 必须是字符串或 null",
        )
        _required_text(raw.get("content"), f"{label}.content")
        source_by_id[web_id] = {
            "web_id": web_id,
            "title": _required_text(raw.get("title"), f"{label}.title"),
            "url": url,
            "source": _required_text(raw.get("source"), f"{label}.source"),
            "source_hint": _required_text(raw.get("source_hint"), f"{label}.source_hint"),
            "published_at": published_at.strip() if isinstance(published_at, str) else None,
        }

    require(isinstance(web_enrichment, dict), "web-enrichment 顶层必须是对象")
    require(
        web_enrichment.get("schema_version") == WEB_ENRICHMENT_SCHEMA,
        f"web-enrichment.schema_version 必须是 {WEB_ENRICHMENT_SCHEMA}",
    )
    enrichment_target = _required_text(
        web_enrichment.get("research_target"), "web-enrichment.research_target"
    )
    require(enrichment_target == target, "web-enrichment 与 dashboard 的研究主题不一致")

    known_ids = set(source_by_id)
    used_ids: set[str] = set()

    raw_background_items = web_enrichment.get("event_background")
    require(isinstance(raw_background_items, list), "web-enrichment.event_background 必须是数组")
    require(len(raw_background_items) <= 4, "event_background 最多保留 4 条")
    event_background: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_background_items):
        label = f"web-enrichment.event_background[{index}]"
        require(isinstance(raw, dict), f"{label} 必须是对象")
        refs = _source_refs(raw.get("source_refs"), f"{label}.source_refs", known_ids)
        used_ids.update(refs)
        event_background.append({
            "text": _required_text(raw.get("text"), f"{label}.text"),
            "source_refs": refs,
        })

    def category_items(field: str) -> list[dict[str, Any]]:
        raw_items = web_enrichment.get(field)
        require(isinstance(raw_items, list), f"web-enrichment.{field} 必须是数组")
        output: list[dict[str, Any]] = []
        seen_categories: set[str] = set()
        for index, raw in enumerate(raw_items):
            label = f"web-enrichment.{field}[{index}]"
            require(isinstance(raw, dict), f"{label} 必须是对象")
            category_id = _required_text(
                raw.get("dashboard_category_id"), f"{label}.dashboard_category_id"
            )
            require(category_id in category_ids, f"{label} 使用未知看板类别：{category_id}")
            require(category_id not in seen_categories, f"{field} 的类别重复：{category_id}")
            seen_categories.add(category_id)
            refs = _source_refs(raw.get("source_refs"), f"{label}.source_refs", known_ids)
            used_ids.update(refs)
            output.append({
                "dashboard_category_id": category_id,
                "text": _required_text(raw.get("text"), f"{label}.text"),
                "source_refs": refs,
            })
        return output

    corroborations = category_items("corroborations")
    counter_signals = category_items("counter_signals")

    raw_limitations = web_enrichment.get("source_limitations")
    require(isinstance(raw_limitations, list), "web-enrichment.source_limitations 必须是数组")
    source_limitations = [
        _required_text(item, f"web-enrichment.source_limitations[{index}]")
        for index, item in enumerate(raw_limitations)
    ]
    raw_declared_ids = web_enrichment.get("used_source_ids")
    require(isinstance(raw_declared_ids, list), "web-enrichment.used_source_ids 必须是数组")
    declared_ids = {
        _required_text(item, f"web-enrichment.used_source_ids[{index}]")
        for index, item in enumerate(raw_declared_ids)
    }
    require(declared_ids == used_ids, "used_source_ids 必须与实际引用的网页来源完全一致")

    context = {
        "status": "enriched" if used_ids else "no_useful_result",
        "candidate_count": len(raw_results),
        "used_source_count": len(used_ids),
        "event_background": event_background,
        "corroborations": corroborations,
        "counter_signals": counter_signals,
        "sources": [source for web_id, source in source_by_id.items() if web_id in used_ids],
        "source_limitations": source_limitations,
    }
    result = json.loads(json.dumps(dashboard, ensure_ascii=False))
    result["schema_version"] = DASHBOARD_SCHEMA
    result["web_context"] = context
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="统一折叠评论输入，并生成可供 UI 使用的确定性洞察看板 JSON。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="生成统一 analysis-input.json")
    prepare.add_argument("--target", required=True, help="本次研究主题")
    prepare.add_argument("--relevance", action="append", type=Path, required=True,
                         help="相关性保留结果；每个平台可传一次或多次")
    prepare.add_argument("--folded", action="append", type=Path, required=True,
                         help="折叠结果；每个平台可传一次或多次")
    prepare.add_argument("--cluster-index", action="append", type=Path, default=[],
                         help="本地链路 cluster-index.json；Dify结果已有成员编号时可省略")
    prepare.add_argument("--output-dir", type=Path, required=True)

    prepare_folded = subparsers.add_parser(
        "prepare-folded",
        help="只使用Dify交付的折叠结果生成统一 analysis-input.json",
    )
    prepare_folded.add_argument("--target", required=True, help="本次研究主题")
    prepare_folded.add_argument("--folded", action="append", type=Path, required=True,
                                help="折叠结果；每个平台传一次")
    prepare_folded.add_argument("--output-dir", type=Path, required=True)

    taxonomy = subparsers.add_parser("validate-taxonomy", help="校验动态分类表")
    taxonomy.add_argument("--classification-plan", type=Path, required=True)
    taxonomy.add_argument("--require-approved", action="store_true")

    finalize = subparsers.add_parser("finalize", help="生成 dashboard.json 与 analysis-audit.json")
    finalize.add_argument("--analysis-input", type=Path, required=True)
    finalize.add_argument("--classification-plan", type=Path, required=True)
    finalize.add_argument("--semantic-analysis", type=Path, required=True)
    finalize.add_argument("--output-dir", type=Path, required=True)

    enrich_web = subparsers.add_parser(
        "enrich-web", help="校验网页补充并写入最终 dashboard.json"
    )
    enrich_web.add_argument("--dashboard", type=Path, required=True)
    enrich_web.add_argument("--web-background", type=Path, required=True)
    enrich_web.add_argument("--web-enrichment", type=Path, required=True)
    enrich_web.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "prepare":
            result = prepare_analysis_input(
                args.target, args.relevance, args.folded, args.cluster_index
            )
            output_path = args.output_dir / "analysis-input.json"
            write_json(output_path, result)
            summary = {
                "ok": True,
                "command": "prepare",
                "output": str(output_path),
                "folded_records": len(result["comments"]),
                "represented_comments": sum(
                    item["represented_count"] for item in result["platforms"]
                ),
            }
        elif args.command == "prepare-folded":
            result = prepare_analysis_input_from_folded(args.target, args.folded)
            output_path = args.output_dir / "analysis-input.json"
            write_json(output_path, result)
            summary = {
                "ok": True,
                "command": "prepare-folded",
                "output": str(output_path),
                "folded_records": len(result["comments"]),
                "represented_comments": sum(
                    item["represented_count"] for item in result["platforms"]
                ),
            }
        elif args.command == "validate-taxonomy":
            plan = validate_taxonomy(
                load_json_file(args.classification_plan), args.require_approved
            )
            summary = {
                "ok": True,
                "command": "validate-taxonomy",
                "status": plan["status"],
                "dynamic_category_count": len(plan["categories"]) - 1,
            }
        elif args.command == "finalize":
            dashboard, audit = finalize_dashboard(
                load_json_file(args.analysis_input),
                load_json_file(args.classification_plan),
                load_json_file(args.semantic_analysis),
            )
            dashboard_path = args.output_dir / "dashboard.json"
            audit_path = args.output_dir / "analysis-audit.json"
            write_json(dashboard_path, dashboard)
            write_json(audit_path, audit)
            summary = {
                "ok": True,
                "command": "finalize",
                "dashboard": str(dashboard_path),
                "audit": str(audit_path),
                "final_analyzed_count": dashboard["counts"]["final_analyzed_count"],
            }
        else:
            dashboard = merge_web_context(
                load_json_file(args.dashboard),
                load_json_file(args.web_background),
                load_json_file(args.web_enrichment),
            )
            dashboard_path = args.output_dir / "dashboard.json"
            write_json(dashboard_path, dashboard)
            summary = {
                "ok": True,
                "command": "enrich-web",
                "dashboard": str(dashboard_path),
                "status": dashboard["web_context"]["status"],
                "candidate_count": dashboard["web_context"]["candidate_count"],
                "used_source_count": dashboard["web_context"]["used_source_count"],
            }
    except DashboardError as exc:
        raise SystemExit(f"看板流程已停止：{exc}") from exc
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
