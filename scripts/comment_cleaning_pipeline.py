"""Deterministic comment-cleaning workflow around two LLM judgment stages.

The script never calls a model itself. It prepares bounded JSON inputs for an
LLM, validates the returned relevance scores and clustering proposals, pauses
for human decisions, and only then renders the minimal final dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


HIGH_THRESHOLD = 0.70
LOW_THRESHOLD = 0.30
SUPPORTED_PLATFORMS = {"douyin", "bilibili", "xiaohongshu"}
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$", re.ASCII)


class CleaningError(ValueError):
    """Raised when an input or a workflow transition is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CleaningError(message)


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CleaningError(f"文件不存在：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CleaningError(f"JSON 无法解析：{path}（{exc}）") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        if not value.endswith("\n"):
            handle.write("\n")


def normalized_comment_mapping(source: Any) -> tuple[str, str | None, dict[str, str]]:
    require(isinstance(source, dict), "简化输入顶层必须是对象")
    platform = source.get("platform")
    require(isinstance(platform, str) and platform, "platform 必须是非空字符串")
    require(platform in SUPPORTED_PLATFORMS, f"暂不支持的平台：{platform}")
    target = source.get("relevance_target")
    if target is not None:
        require(isinstance(target, str), "relevance_target 必须是字符串或 null")
        target = target.strip() or None

    comments = source.get("comments")
    require(isinstance(comments, dict), "comments 必须是编号到评论的对象")
    normalized: dict[str, str] = {}
    for record_id, value in comments.items():
        require(isinstance(record_id, str) and ID_PATTERN.fullmatch(record_id) is not None,
                f"评论编号非法：{record_id!r}")
        require(record_id not in normalized, f"评论编号重复：{record_id}")
        if isinstance(value, str):
            text = value
        else:
            require(isinstance(value, dict), f"{record_id} 的评论值必须是字符串或对象")
            text = value.get("text")
        require(isinstance(text, str), f"{record_id}.text 必须是字符串")
        normalized[record_id] = text
    return platform, target, normalized


def prepare(input_path: Path, run_dir: Path, target_override: str | None) -> dict[str, Any]:
    platform, source_target, comments = normalized_comment_mapping(read_json(input_path))
    target = (target_override or "").strip() or source_target
    require(isinstance(target, str) and target.strip(),
            "必须通过 --target 或输入 relevance_target 提供研究主题")

    kept: list[dict[str, str]] = []
    empty_ids: list[str] = []
    for record_id, text in comments.items():
        if not text.strip():
            empty_ids.append(record_id)
        else:
            kept.append({"record_id": record_id, "text": text})

    request = {
        "schema_version": "comment-relevance-request-1.0",
        "platform": platform,
        "research_target": target.strip(),
        "comments": kept,
    }
    excluded = {
        "schema_version": "hard-excluded-1.0",
        "platform": platform,
        "items": [
            {"record_id": record_id, "reason": "empty_text"}
            for record_id in empty_ids
        ],
    }
    write_json(run_dir / "relevance-request.json", request)
    write_json(run_dir / "hard-excluded.json", excluded)
    return {
        "platform": platform,
        "input_count": len(comments),
        "request_count": len(kept),
        "empty_excluded_count": len(empty_ids),
    }


def load_relevance_request(run_dir: Path) -> dict[str, Any]:
    value = read_json(run_dir / "relevance-request.json")
    require(isinstance(value, dict), "relevance-request.json 顶层必须是对象")
    require(value.get("schema_version") == "comment-relevance-request-1.0",
            "relevance-request.json 版本不受支持")
    require(isinstance(value.get("platform"), str), "relevance-request.platform 非法")
    require(isinstance(value.get("research_target"), str)
            and value["research_target"].strip(), "research_target 不能为空")
    comments = value.get("comments")
    require(isinstance(comments, list), "relevance-request.comments 必须是数组")
    seen: set[str] = set()
    for index, item in enumerate(comments):
        require(isinstance(item, dict), f"comments[{index}] 必须是对象")
        record_id = item.get("record_id")
        require(isinstance(record_id, str) and record_id not in seen,
                f"comments[{index}].record_id 非法或重复")
        require(isinstance(item.get("text"), str) and item["text"].strip(),
                f"{record_id}.text 不能为空")
        seen.add(record_id)
    return value


@dataclass(frozen=True)
class ScoreResult:
    record_id: str
    score: float
    reason: str | None

    @property
    def route(self) -> str:
        if self.score >= HIGH_THRESHOLD:
            return "keep"
        if self.score < LOW_THRESHOLD:
            return "exclude"
        return "review"


def validate_scores(raw: Any, expected_ids: Iterable[str]) -> list[ScoreResult]:
    require(isinstance(raw, dict), "相关性输出顶层必须是对象")
    results = raw.get("results")
    require(isinstance(results, list), "相关性输出必须包含 results 数组")
    expected = list(expected_ids)
    expected_set = set(expected)
    by_id: dict[str, ScoreResult] = {}

    for index, item in enumerate(results):
        require(isinstance(item, dict), f"results[{index}] 必须是对象")
        allowed = {"record_id", "relevance_score", "reason"}
        require(set(item).issubset(allowed), f"results[{index}] 包含未知字段")
        record_id = item.get("record_id")
        require(isinstance(record_id, str), f"results[{index}].record_id 必须是字符串")
        require(record_id in expected_set, f"LLM 返回了未知编号：{record_id}")
        require(record_id not in by_id, f"LLM 重复返回编号：{record_id}")
        score = item.get("relevance_score")
        require(isinstance(score, (int, float)) and not isinstance(score, bool)
                and math.isfinite(float(score)) and 0 <= float(score) <= 1,
                f"{record_id}.relevance_score 必须是 0—1 的有限数字")
        score_value = float(score)
        in_review = LOW_THRESHOLD <= score_value < HIGH_THRESHOLD
        reason = item.get("reason")
        if in_review:
            require(isinstance(reason, str) and reason.strip(),
                    f"{record_id} 位于人工审核区间，必须提供非空 reason")
            reason = reason.strip()
        else:
            require("reason" not in item,
                    f"{record_id} 不在人工审核区间，不应返回 reason")
            reason = None
        by_id[record_id] = ScoreResult(record_id, score_value, reason)

    missing = [record_id for record_id in expected if record_id not in by_id]
    require(not missing, f"LLM 漏掉了编号：{', '.join(missing[:10])}")
    require(len(by_id) == len(expected), "相关性结果数量与输入不一致")
    return [by_id[record_id] for record_id in expected]


def route_relevance(run_dir: Path, scores_path: Path) -> dict[str, int]:
    request = load_relevance_request(run_dir)
    text_by_id = {item["record_id"]: item["text"] for item in request["comments"]}
    scores = validate_scores(read_json(scores_path), text_by_id)

    auto_kept: list[dict[str, Any]] = []
    auto_excluded: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    normalized_scores: list[dict[str, Any]] = []
    for result in scores:
        base = {
            "record_id": result.record_id,
            "relevance_score": result.score,
        }
        if result.reason is not None:
            base["reason"] = result.reason
        normalized_scores.append(base)
        if result.route == "keep":
            auto_kept.append(base)
        elif result.route == "exclude":
            auto_excluded.append(base)
        else:
            review_items.append({
                "record_id": result.record_id,
                "text": text_by_id[result.record_id],
                "relevance_score": result.score,
                "reason": result.reason,
                "human_decision": "pending",
            })

    write_json(run_dir / "relevance-scores.json", {
        "schema_version": "relevance-scores-1.0",
        "results": normalized_scores,
    })
    write_json(run_dir / "relevance-routing.json", {
        "schema_version": "relevance-routing-1.0",
        "platform": request["platform"],
        "research_target": request["research_target"],
        "auto_kept": auto_kept,
        "auto_excluded": auto_excluded,
    })
    write_json(run_dir / "relevance-review.json", {
        "schema_version": "relevance-review-1.0",
        "platform": request["platform"],
        "research_target": request["research_target"],
        "items": review_items,
    })
    return {
        "auto_kept": len(auto_kept),
        "pending_review": len(review_items),
        "auto_excluded": len(auto_excluded),
    }


def finalize_relevance(run_dir: Path) -> dict[str, int]:
    request = load_relevance_request(run_dir)
    routing = read_json(run_dir / "relevance-routing.json")
    review = read_json(run_dir / "relevance-review.json")
    require(isinstance(routing, dict)
            and routing.get("schema_version") == "relevance-routing-1.0",
            "relevance-routing.json 非法或版本不受支持")
    require(isinstance(review, dict)
            and review.get("schema_version") == "relevance-review-1.0",
            "relevance-review.json 非法或版本不受支持")
    require(routing.get("platform") == request["platform"]
            and review.get("platform") == request["platform"], "平台字段不一致")
    require(routing.get("research_target") == request["research_target"]
            and review.get("research_target") == request["research_target"], "研究主题不一致")

    text_by_id = {item["record_id"]: item["text"] for item in request["comments"]}
    validated_scores = validate_scores(
        read_json(run_dir / "relevance-scores.json"), text_by_id
    )
    expected_by_id = {item.record_id: item for item in validated_scores}
    expected_auto_keep_ids = {
        item.record_id for item in validated_scores if item.route == "keep"
    }
    expected_auto_excluded_ids = {
        item.record_id for item in validated_scores if item.route == "exclude"
    }
    expected_review_ids = {
        item.record_id for item in validated_scores if item.route == "review"
    }
    auto_kept = routing.get("auto_kept")
    auto_excluded = routing.get("auto_excluded")
    review_items = review.get("items")
    require(isinstance(auto_kept, list) and isinstance(auto_excluded, list),
            "relevance-routing 的分流数组非法")
    require(isinstance(review_items, list), "relevance-review.items 必须是数组")

    decisions: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(review_items):
        require(isinstance(item, dict), f"review.items[{index}] 必须是对象")
        record_id = item.get("record_id")
        require(isinstance(record_id, str) and record_id in text_by_id,
                f"审核项编号非法：{record_id!r}")
        require(record_id not in decisions, f"审核项编号重复：{record_id}")
        require(item.get("text") == text_by_id[record_id], f"{record_id} 的审核原文被修改")
        expected = expected_by_id[record_id]
        require(record_id in expected_review_ids, f"{record_id} 不属于人工审核区间")
        require(item.get("relevance_score") == expected.score,
                f"{record_id} 的相关性分数被修改")
        require(item.get("reason") == expected.reason, f"{record_id} 的审核理由被修改")
        decision = item.get("human_decision")
        require(decision in {"keep", "exclude"},
                f"{record_id}.human_decision 必须完成为 keep 或 exclude")
        decisions[record_id] = item

    auto_keep_by_id: dict[str, dict[str, Any]] = {}
    auto_excluded_ids: set[str] = set()
    for item in auto_kept:
        require(isinstance(item, dict) and isinstance(item.get("record_id"), str),
                "auto_kept 项非法")
        record_id = item["record_id"]
        require(record_id in text_by_id and record_id not in auto_keep_by_id,
                f"auto_kept 编号非法或重复：{record_id}")
        require(record_id in expected_auto_keep_ids
                and item.get("relevance_score") == expected_by_id[record_id].score,
                f"auto_kept 内容与已验证分数不一致：{record_id}")
        auto_keep_by_id[record_id] = item
    for item in auto_excluded:
        require(isinstance(item, dict) and isinstance(item.get("record_id"), str),
                "auto_excluded 项非法")
        record_id = item["record_id"]
        require(record_id in text_by_id and record_id not in auto_excluded_ids,
                f"auto_excluded 编号非法或重复：{record_id}")
        require(record_id in expected_auto_excluded_ids
                and item.get("relevance_score") == expected_by_id[record_id].score,
                f"auto_excluded 内容与已验证分数不一致：{record_id}")
        auto_excluded_ids.add(record_id)

    all_ids = set(text_by_id)
    require(set(auto_keep_by_id) == expected_auto_keep_ids,
            "auto_kept 没有完整匹配已验证分数")
    require(auto_excluded_ids == expected_auto_excluded_ids,
            "auto_excluded 没有完整匹配已验证分数")
    require(set(decisions) == expected_review_ids,
            "人工审核项没有完整匹配中间分数区间")
    require(set(auto_keep_by_id) | auto_excluded_ids | set(decisions) == all_ids,
            "分流和人工审核没有完整覆盖相关性输入")
    require(not (set(auto_keep_by_id) & auto_excluded_ids)
            and not (set(auto_keep_by_id) & set(decisions))
            and not (auto_excluded_ids & set(decisions)), "相关性分流存在交叉编号")

    kept_comments: dict[str, dict[str, Any]] = {}
    human_kept = 0
    for record_id, text in text_by_id.items():
        if record_id in auto_keep_by_id:
            kept_comments[record_id] = {
                "text": text,
                "relevance_score": auto_keep_by_id[record_id]["relevance_score"],
                "review_status": "auto_accepted",
            }
        elif record_id in decisions and decisions[record_id]["human_decision"] == "keep":
            kept_comments[record_id] = {
                "text": text,
                "relevance_score": decisions[record_id]["relevance_score"],
                "review_status": "human_accepted",
            }
            human_kept += 1

    result = {
        "schema_version": "relevance-result-1.0",
        "platform": request["platform"],
        "research_target": request["research_target"],
        "comments": kept_comments,
    }
    cluster_request = {
        "schema_version": "cluster-request-1.0",
        "platform": request["platform"],
        "research_target": request["research_target"],
        "comments": [
            {"record_id": record_id, "text": value["text"]}
            for record_id, value in kept_comments.items()
        ],
    }
    write_json(run_dir / "relevance-result.json", result)
    write_json(run_dir / "cluster-request.json", cluster_request)
    return {
        "kept_total": len(kept_comments),
        "auto_kept": len(auto_keep_by_id),
        "human_kept": human_kept,
    }


def load_relevance_result(run_dir: Path) -> dict[str, Any]:
    value = read_json(run_dir / "relevance-result.json")
    require(isinstance(value, dict)
            and value.get("schema_version") == "relevance-result-1.0",
            "relevance-result.json 非法或版本不受支持")
    require(isinstance(value.get("comments"), dict), "relevance-result.comments 必须是对象")
    for record_id, item in value["comments"].items():
        require(isinstance(record_id, str) and isinstance(item, dict), "相关性保留项非法")
        require(isinstance(item.get("text"), str) and item["text"].strip(),
                f"{record_id}.text 不能为空")
    return value


def validate_cluster_proposals(raw: Any, comments: dict[str, Any]) -> list[dict[str, Any]]:
    require(isinstance(raw, dict), "聚类提案顶层必须是对象")
    clusters = raw.get("clusters")
    require(isinstance(clusters, list), "聚类提案必须包含 clusters 数组")
    all_ids = set(comments)
    used_members: set[str] = set()
    seen_clusters: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters):
        prefix = f"clusters[{index}]"
        require(isinstance(cluster, dict), f"{prefix} 必须是对象")
        allowed = {"cluster_id", "representative_id", "member_ids",
                   "shared_viewpoint", "merge_basis"}
        require(set(cluster) == allowed, f"{prefix} 字段不完整或包含未知字段")
        cluster_id = cluster["cluster_id"]
        require(isinstance(cluster_id, str) and ID_PATTERN.fullmatch(cluster_id) is not None,
                f"{prefix}.cluster_id 非法")
        require(cluster_id not in seen_clusters, f"cluster_id 重复：{cluster_id}")
        seen_clusters.add(cluster_id)
        member_ids = cluster["member_ids"]
        require(isinstance(member_ids, list) and len(member_ids) >= 2,
                f"{cluster_id}.member_ids 至少包含两项")
        require(all(isinstance(item, str) for item in member_ids),
                f"{cluster_id}.member_ids 必须全部是字符串")
        require(len(member_ids) == len(set(member_ids)), f"{cluster_id} 内部成员重复")
        unknown = [item for item in member_ids if item not in all_ids]
        require(not unknown, f"{cluster_id} 包含未知成员：{', '.join(unknown)}")
        overlap = [item for item in member_ids if item in used_members]
        require(not overlap, f"评论被多个聚类重复使用：{', '.join(overlap)}")
        used_members.update(member_ids)
        representative_id = cluster["representative_id"]
        require(representative_id in member_ids,
                f"{cluster_id}.representative_id 必须属于 member_ids")
        shared = cluster["shared_viewpoint"]
        require(isinstance(shared, str) and shared.strip(),
                f"{cluster_id}.shared_viewpoint 不能为空")
        basis = cluster["merge_basis"]
        require(isinstance(basis, list) and len(basis) >= 3
                and all(isinstance(item, str) and item.strip() for item in basis),
                f"{cluster_id}.merge_basis 至少需要三条非空依据")
        normalized.append({
            "cluster_id": cluster_id,
            "representative_id": representative_id,
            "members": [
                {"record_id": record_id, "text": comments[record_id]["text"]}
                for record_id in member_ids
            ],
            "shared_viewpoint": shared.strip(),
            "merge_basis": [item.strip() for item in basis],
            "decision": "pending",
            "accepted_member_ids": [],
        })
    return normalized


def render_cluster_review(review: dict[str, Any]) -> str:
    lines = [
        "# 高同质评论折叠审核",
        "",
        f"- 平台：{review['platform']}",
        f"- 研究主题：{review['research_target']}",
        f"- 待审核聚类：{len(review['clusters'])}",
        "",
        "请在 `cluster-review.json` 中把每组 decision 改为 "
        "`merge_all`、`keep_separate` 或 `merge_selected`。",
        "",
    ]
    for cluster in review["clusters"]:
        lines.extend([
            f"## {cluster['cluster_id']}",
            "",
            f"**共同观点（仅作合并说明）**：{cluster['shared_viewpoint']}",
            "",
            f"**建议代表编号**：{cluster['representative_id']}",
            "",
            "**合并依据**：",
            "",
        ])
        lines.extend(f"- {basis}" for basis in cluster["merge_basis"])
        lines.extend(["", "**全部真实原文**：", ""])
        for member in cluster["members"]:
            quote = member["text"].replace("\n", " ")
            lines.append(f"- `{member['record_id']}`：{quote}")
        lines.extend(["", "**人工决定**：pending", "", "---", ""])
    return "\n".join(lines)


def build_cluster_review(run_dir: Path, proposals_path: Path) -> dict[str, int]:
    relevance = load_relevance_result(run_dir)
    clusters = validate_cluster_proposals(read_json(proposals_path), relevance["comments"])
    review = {
        "schema_version": "cluster-review-1.0",
        "platform": relevance["platform"],
        "research_target": relevance["research_target"],
        "clusters": clusters,
    }
    write_json(run_dir / "cluster-proposals.json", {
        "schema_version": "cluster-proposals-1.0",
        "clusters": [
            {
                "cluster_id": cluster["cluster_id"],
                "representative_id": cluster["representative_id"],
                "member_ids": [member["record_id"] for member in cluster["members"]],
                "shared_viewpoint": cluster["shared_viewpoint"],
                "merge_basis": cluster["merge_basis"],
            }
            for cluster in clusters
        ],
    })
    write_json(run_dir / "cluster-review.json", review)
    write_text(run_dir / "cluster-review.md", render_cluster_review(review))
    return {
        "proposal_count": len(clusters),
        "pending_review": len(clusters),
        "unclustered_count": len(relevance["comments"])
        - sum(len(cluster["members"]) for cluster in clusters),
    }


def finalize_clusters(run_dir: Path) -> dict[str, int]:
    relevance = load_relevance_result(run_dir)
    review = read_json(run_dir / "cluster-review.json")
    require(isinstance(review, dict)
            and review.get("schema_version") == "cluster-review-1.0",
            "cluster-review.json 非法或版本不受支持")
    require(review.get("platform") == relevance["platform"]
            and review.get("research_target") == relevance["research_target"],
            "聚类审核与相关性结果不属于同一任务")
    clusters = review.get("clusters")
    require(isinstance(clusters, list), "cluster-review.clusters 必须是数组")

    proposals = read_json(run_dir / "cluster-proposals.json")
    require(isinstance(proposals, dict)
            and proposals.get("schema_version") == "cluster-proposals-1.0"
            and isinstance(proposals.get("clusters"), list),
            "cluster-proposals.json 非法或版本不受支持")
    proposal_by_id = {
        item.get("cluster_id"): item
        for item in proposals["clusters"]
        if isinstance(item, dict) and isinstance(item.get("cluster_id"), str)
    }
    require(len(proposal_by_id) == len(proposals["clusters"]),
            "cluster-proposals.json 存在非法或重复 cluster_id")
    review_ids = [
        item.get("cluster_id") for item in clusters if isinstance(item, dict)
    ]
    require(len(review_ids) == len(clusters) and set(review_ids) == set(proposal_by_id),
            "cluster-review.json 的聚类集合被修改")

    comments = relevance["comments"]
    consumed: set[str] = set()
    merge_by_member: dict[str, dict[str, Any]] = {}
    cluster_index: dict[str, dict[str, Any]] = {}
    seen_clusters: set[str] = set()

    for index, cluster in enumerate(clusters):
        prefix = f"clusters[{index}]"
        require(isinstance(cluster, dict), f"{prefix} 必须是对象")
        cluster_id = cluster.get("cluster_id")
        require(isinstance(cluster_id, str) and cluster_id not in seen_clusters,
                f"{prefix}.cluster_id 非法或重复")
        seen_clusters.add(cluster_id)
        members = cluster.get("members")
        require(isinstance(members, list) and len(members) >= 2,
                f"{cluster_id}.members 至少包含两项")
        member_ids: list[str] = []
        for member in members:
            require(isinstance(member, dict) and isinstance(member.get("record_id"), str),
                    f"{cluster_id} 成员非法")
            record_id = member["record_id"]
            require(record_id in comments, f"{cluster_id} 包含未知成员：{record_id}")
            require(member.get("text") == comments[record_id]["text"],
                    f"{cluster_id} 的 {record_id} 原文被修改")
            require(record_id not in member_ids, f"{cluster_id} 内部成员重复：{record_id}")
            member_ids.append(record_id)
        proposal = proposal_by_id[cluster_id]
        require(member_ids == proposal.get("member_ids"),
                f"{cluster_id} 的成员列表被修改；请使用 merge_selected 选择子集")
        require(cluster.get("shared_viewpoint") == proposal.get("shared_viewpoint")
                and cluster.get("merge_basis") == proposal.get("merge_basis"),
                f"{cluster_id} 的 LLM 合并说明被修改")
        decision = cluster.get("decision")
        require(decision in {"merge_all", "keep_separate", "merge_selected"},
                f"{cluster_id}.decision 尚未完成")
        accepted = cluster.get("accepted_member_ids")
        require(isinstance(accepted, list)
                and all(isinstance(item, str) for item in accepted),
                f"{cluster_id}.accepted_member_ids 必须是字符串数组")
        if decision == "merge_all":
            require(not accepted or accepted == member_ids,
                    f"{cluster_id} merge_all 时 accepted_member_ids 应为空或等于全部成员")
            selected = member_ids
        elif decision == "keep_separate":
            require(not accepted, f"{cluster_id} keep_separate 时不得填写 accepted_member_ids")
            selected = []
        else:
            require(len(accepted) >= 2 and len(accepted) < len(member_ids),
                    f"{cluster_id} merge_selected 必须选择至少两项且不能等于全部成员")
            require(len(accepted) == len(set(accepted))
                    and set(accepted).issubset(member_ids),
                    f"{cluster_id}.accepted_member_ids 包含重复或非成员编号")
            selected = accepted

        if not selected:
            continue
        representative_id = cluster.get("representative_id")
        require(representative_id in selected,
                f"{cluster_id}.representative_id 必须属于最终合并成员")
        overlap = [item for item in selected if item in consumed]
        require(not overlap, f"评论被多个已批准聚类重复使用：{', '.join(overlap)}")
        consumed.update(selected)
        merged = {
            "cluster_id": cluster_id,
            "representative_id": representative_id,
            "member_ids": selected,
            "support_count": len(selected),
        }
        cluster_index[cluster_id] = merged
        for record_id in selected:
            merge_by_member[record_id] = merged

    final_comments: dict[str, dict[str, Any]] = {}
    emitted_clusters: set[str] = set()
    for record_id, item in comments.items():
        merged = merge_by_member.get(record_id)
        if merged is None:
            final_comments[record_id] = {"text": item["text"], "support_count": 1}
            continue
        cluster_id = merged["cluster_id"]
        if cluster_id in emitted_clusters:
            continue
        representative_id = merged["representative_id"]
        final_comments[representative_id] = {
            "text": comments[representative_id]["text"],
            "support_count": merged["support_count"],
        }
        emitted_clusters.add(cluster_id)

    final_output = {
        "platform": relevance["platform"],
        "comments": final_comments,
    }
    report = {
        "schema_version": "comment-cleaning-report-1.0",
        "platform": relevance["platform"],
        "research_target": relevance["research_target"],
        "relevant_input_count": len(comments),
        "approved_cluster_count": len(cluster_index),
        "final_record_count": len(final_comments),
        "represented_comment_count": sum(
            item["support_count"] for item in final_comments.values()
        ),
    }
    write_json(run_dir / "cluster-index.json", {
        "schema_version": "cluster-index-1.0",
        "platform": relevance["platform"],
        "clusters": cluster_index,
    })
    write_json(run_dir / "final-cleaned-comments.json", final_output)
    write_json(run_dir / "cleaning-report.json", report)
    return {
        "approved_clusters": len(cluster_index),
        "final_records": len(final_comments),
        "represented_comments": report["represented_comment_count"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="评论相关性清洗与高同质折叠的确定性工作流。"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="删除空评论并准备相关性 LLM 输入")
    prepare_parser.add_argument("--input", type=Path, required=True, help="简化编号 JSON")
    prepare_parser.add_argument("--run-dir", type=Path, required=True, help="本次清洗运行目录")
    prepare_parser.add_argument("--target", default=None, help="研究主题；覆盖输入中的 relevance_target")

    route_parser = subparsers.add_parser("route-relevance", help="校验 LLM 分数并生成审核队列")
    route_parser.add_argument("--run-dir", type=Path, required=True)
    route_parser.add_argument("--scores", type=Path, required=True, help="LLM 相关性输出 JSON")

    finalize_relevance_parser = subparsers.add_parser(
        "finalize-relevance", help="合并人工决定并准备聚类输入"
    )
    finalize_relevance_parser.add_argument("--run-dir", type=Path, required=True)

    cluster_parser = subparsers.add_parser(
        "build-cluster-review", help="校验 LLM 聚类提案并生成人工审核文件"
    )
    cluster_parser.add_argument("--run-dir", type=Path, required=True)
    cluster_parser.add_argument("--proposals", type=Path, required=True, help="LLM 聚类提案 JSON")

    finalize_parser = subparsers.add_parser(
        "finalize", help="应用人工批准的折叠并生成最终极简 JSON"
    )
    finalize_parser.add_argument("--run-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.input, args.run_dir, args.target)
        elif args.command == "route-relevance":
            result = route_relevance(args.run_dir, args.scores)
        elif args.command == "finalize-relevance":
            result = finalize_relevance(args.run_dir)
        elif args.command == "build-cluster-review":
            result = build_cluster_review(args.run_dir, args.proposals)
        else:
            result = finalize_clusters(args.run_dir)
    except CleaningError as exc:
        raise SystemExit(f"清洗流程已停止：{exc}") from exc
    print(json.dumps({"ok": True, "command": args.command, **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
