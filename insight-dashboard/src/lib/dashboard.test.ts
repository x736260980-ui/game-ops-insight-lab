import { describe, expect, it } from "vitest";
import {
  filterAndSortRuns,
  formatDate,
  formatInteger,
  formatPercent,
  normalizeDashboard,
  normalizeCategoryCommentResult,
  normalizeRunSummary,
  platformLabel,
  runListState,
  sentimentEntries,
  sortCategoryStats,
  sortCategories,
  webItemsForCategory,
} from "./dashboard";

describe("dashboard data adapter", () => {
  it("normalizes a malformed list item without throwing", () => {
    expect(normalizeRunSummary(null, 2)).toMatchObject({
      runId: "unknown-2",
      title: "未命名调查",
      platforms: [],
      finalCount: 0,
      categoryCount: 0,
      status: "error",
    });
  });

  it("normalizes object platform labels and numeric fields", () => {
    expect(normalizeRunSummary({
      run_id: "r1",
      research_target: "知更鸟研究",
      generated_at: "2026-08-23T12:00:00Z",
      platforms: [{ platform: "bilibili" }, "douyin", {}],
      final_analyzed_count: "247",
      category_count: 6,
      status: "ready",
    }, 0)).toMatchObject({
      runId: "r1",
      title: "知更鸟研究",
      platforms: ["bilibili", "douyin"],
      finalCount: 247,
      categoryCount: 6,
      status: "ready",
    });
  });

  it("filters titles case-insensitively and sorts dates both ways", () => {
    const items = [
      normalizeRunSummary({ run_id: "old", research_target: "ROBIN 旧研究", generated_at: "2026-01-01" }, 0),
      normalizeRunSummary({ run_id: "new", research_target: "Robin 新研究", generated_at: "2026-08-01" }, 1),
      normalizeRunSummary({ run_id: "other", research_target: "流萤研究", generated_at: "2026-09-01" }, 2),
    ];
    expect(filterAndSortRuns(items, " robin ", "newest").map((item) => item.runId)).toEqual(["new", "old"]);
    expect(filterAndSortRuns(items, "ROBIN", "oldest").map((item) => item.runId)).toEqual(["old", "new"]);
  });

  it("sorts categories by count while preserving source order on ties", () => {
    const categories = sortCategories([
      { category_id: "a", name: "A", count: 5 },
      { category_id: "b", name: "B", count: 9 },
      { category_id: "c", name: "C", count: 5 },
    ]);
    expect(categories.map((category) => category.id)).toEqual(["b", "a", "c"]);
  });

  it("sorts normalized categories by negative feedback count", () => {
    const categories = sortCategories([
      { category_id: "popular", name: "讨论多", count: 20, sentiment: { negative: { count: 2 } } },
      { category_id: "risk", name: "负面多", count: 10, sentiment: { negative: { count: 7 } } },
      { category_id: "tie", name: "同为负面多", count: 8, sentiment: { negative: { count: 7 } } },
    ]);
    expect(sortCategoryStats(categories, "negative").map((category) => category.id)).toEqual(["risk", "tie", "popular"]);
  });

  it("normalizes a sparse dashboard and caps representative comments at two", () => {
    const dashboard = normalizeDashboard({
      run_id: "r2",
      categories: [{
        category_id: "x",
        name: "配队",
        count: 2,
        representative_comments: [
          { record_id: "1", text: "一", support_count: 3 },
          { record_id: "2", text: "二" },
          { record_id: "3", text: "三" },
        ],
      }],
    });
    expect(dashboard.title).toBe("未命名调查");
    expect(dashboard.categories[0].comments).toHaveLength(2);
    expect(dashboard.categories[0].comments[0].supportCount).toBe(3);
    expect(dashboard.counts.finalAnalyzed).toBe(0);
  });

  it("normalizes the authoritative analysis summary and keeps the full research question", () => {
    const dashboard = normalizeDashboard({
      research_target: "完整研究问题",
      analysis_summary: {
        schema_version: "game-ops-final-summary-1.0",
        research_title: "绯英 PV 争议",
        core_judgment: "质量不足被规格差异升级为待遇不公叙事。",
        risk: { score: 0.6, level: "middle", rationale: "风险集中。" },
        confidence: { level: "middle", rationale: "官方证据不足。" },
        key_findings: ["基础体验伤口明确"],
        operation_directions: ["补足角色表达"],
        evidence_refs: ["XHS-1"],
        evidence_gaps: ["缺少官方说明"],
      },
      comment_drilldown_available: true,
    });
    expect(dashboard.title).toBe("绯英 PV 争议");
    expect(dashboard.researchQuestion).toBe("完整研究问题");
    expect(dashboard.analysisSummary?.risk).toEqual({ score: 0.6, level: "middle", rationale: "风险集中。" });
    expect(dashboard.commentDrilldownAvailable).toBe(true);
  });

  it("normalizes category drill-down counts and localized platform labels", () => {
    const result = normalizeCategoryCommentResult({
      category_id: "pv_quality",
      sentiment: "negative",
      weighted_expression_count: 4,
      representative_record_count: 2,
      records: [
        { record_id: "XHS-1", platform: "xiaohongshu", text: "太短了", support_count: 3 },
        { record_id: "BILI-1", platform: "bilibili", text: "没记忆点", support_count: 1 },
      ],
    });
    expect(result.weightedExpressionCount).toBe(4);
    expect(result.representativeRecordCount).toBe(2);
    expect(result.records[0].supportCount).toBe(3);
    expect(platformLabel("xiaohongshu")).toBe("小红书");
    expect(platformLabel("douyin")).toBe("抖音");
    expect(platformLabel("bilibili")).toBe("Bilibili");
  });

  it("formats dates, integers, ratios, and sentiment consistently", () => {
    expect(formatDate("not-a-date")).toBe("日期未知");
    expect(formatInteger(12345)).toBe("12,345");
    expect(formatPercent(0.4332)).toBe("43.3%");
    expect(sentimentEntries({ positive: { count: 2, ratio: .2 } }).map((item) => item.count)).toEqual([2, 0, 0, 0]);
  });

  it("derives sentiment ratios from counts when ratios are missing or inconsistent", () => {
    expect(sentimentEntries({
      positive: { count: 3 },
      negative: { count: 1 },
    }).map((item) => item.ratio)).toEqual([0.75, 0.25, 0, 0]);

    expect(sentimentEntries({
      positive: { count: 1, ratio: 0.8 },
      negative: { count: 1, ratio: 0.8 },
    }).map((item) => item.ratio)).toEqual([0.5, 0.5, 0, 0]);
  });

  it("recalculates sentiment ratios from counts when supplied ratios are zero or disagree", () => {
    expect(sentimentEntries({
      positive: { count: 3, ratio: 0 },
      negative: { count: 1, ratio: 0 },
      neutral: { count: 0, ratio: 0 },
      mixed: { count: 0, ratio: 0 },
    }).map((item) => item.ratio)).toEqual([0.75, 0.25, 0, 0]);

    expect(sentimentEntries({
      positive: { count: 3, ratio: 0.5 },
      negative: { count: 1, ratio: 0.5 },
      neutral: { count: 0, ratio: 0 },
      mixed: { count: 0, ratio: 0 },
    }).map((item) => item.ratio)).toEqual([0.75, 0.25, 0, 0]);
  });

  it("shows only the list error when the first API request fails", () => {
    expect(runListState({ runCount: 0, visibleCount: 0, loading: false, error: "网络不可用" })).toBe("error");
    expect(runListState({ runCount: 0, visibleCount: 0, loading: false, error: "" })).toBe("empty");
  });

  it("hides absent or unusable web context for backward-compatible dashboards", () => {
    expect(normalizeDashboard({ schema_version: "game-comment-dashboard-1.0" }).webContext).toBeNull();
    expect(normalizeDashboard({
      schema_version: "game-comment-dashboard-1.1",
      web_context: {
        status: "no_useful_result",
        candidate_count: 12,
        used_source_count: 0,
      },
    }).webContext).toBeNull();
  });

  it("normalizes enriched web context and keeps category evidence scoped", () => {
    const dashboard = normalizeDashboard({
      web_context: {
        status: "enriched",
        candidate_count: 22,
        used_source_count: 3,
        event_background: [
          { text: "官方公开了角色定位。", source_refs: ["WEB-001"] },
        ],
        corroborations: [
          { dashboard_category_id: "pull_value", text: "其他社区也讨论资源取舍。", source_refs: ["WEB-002"] },
          { dashboard_category_id: "combat", text: "另一类别的补充。", source_refs: ["WEB-003"] },
        ],
        counter_signals: [
          { dashboard_category_id: "pull_value", text: "也有观点认为应等待实测。", source_refs: ["WEB-003"] },
        ],
        sources: [
          { web_id: "WEB-001", title: "官方介绍", url: "https://example.com/1", source: "官网", source_hint: "official", published_at: "2026-08-20" },
          { web_id: "WEB-002", title: "社区讨论", url: "https://example.com/2", source: "TapTap", source_hint: "taptap", published_at: null },
          { web_id: "WEB-003", title: "另一观点", url: "https://example.com/3", source: "NGA", source_hint: "nga", published_at: null },
        ],
        source_limitations: ["网页资料只作定性参考。"],
      },
    });

    expect(dashboard.webContext).not.toBeNull();
    expect(dashboard.webContext?.candidateCount).toBe(22);
    expect(dashboard.webContext?.eventBackground[0].sourceRefs).toEqual(["WEB-001"]);
    expect(dashboard.webContext?.sources[0].webId).toBe("WEB-001");
    expect(webItemsForCategory(dashboard.webContext, "pull_value")).toEqual({
      corroboration: expect.objectContaining({ text: "其他社区也讨论资源取舍。" }),
      counterSignal: expect.objectContaining({ text: "也有观点认为应等待实测。" }),
    });
  });

  it("keeps existing legacy web context visible without rewriting run data", () => {
    const dashboard = normalizeDashboard({
      web_context: {
        event_background: [{ text: "旧版背景", source_refs: ["WEB-001"] }],
        corroborations: [],
        counter_signals: [],
        sources: [{
          id: "WEB-001",
          title: "旧版来源",
          url: "https://example.com/legacy",
          kind: "community",
          summary: "旧版来源摘要",
        }],
        source_limitations: ["旧版资料仅作参考。"],
      },
    });

    expect(dashboard.webContext?.usedSourceCount).toBe(1);
    expect(dashboard.webContext?.candidateCount).toBe(1);
    expect(dashboard.webContext?.sources[0]).toMatchObject({
      webId: "WEB-001",
      sourceHint: "community",
    });
  });
});
