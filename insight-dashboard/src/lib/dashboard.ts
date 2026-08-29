export type SortOrder = "newest" | "oldest";
export type CategorySortOrder = "volume" | "negative";
export type SentimentKey = "positive" | "negative" | "neutral" | "mixed";
export type RunListState = "loading" | "error" | "results" | "no-matches" | "empty";

export interface RunSummary {
  runId: string;
  title: string;
  generatedAt: string;
  platforms: string[];
  finalCount: number;
  categoryCount: number;
  status: "ready" | "error";
  error?: string;
}

export interface SentimentItem {
  key: SentimentKey;
  label: string;
  count: number;
  ratio: number;
  color: string;
}

export interface PlatformStat {
  platform: string;
  relevanceCount: number;
  foldedCount: number;
  includedCount: number;
}

export interface RepresentativeComment {
  recordId: string;
  platform: string;
  text: string;
  supportCount: number;
}

export type RiskLevel = "low" | "middle" | "high";

export interface AnalysisSummary {
  schemaVersion: string;
  researchTitle: string;
  coreJudgment: string;
  risk: { score: number; level: RiskLevel; rationale: string };
  confidence: { level: RiskLevel; rationale: string };
  keyFindings: string[];
  operationDirections: string[];
  evidenceRefs: string[];
  evidenceGaps: string[];
}

export interface CategoryCommentResult {
  categoryId: string;
  sentiment: SentimentKey;
  weightedExpressionCount: number;
  representativeRecordCount: number;
  records: RepresentativeComment[];
}

export interface CategoryStat {
  id: string;
  name: string;
  count: number;
  ratio: number;
  summary: string;
  sentiment: unknown;
  comments: RepresentativeComment[];
}

export interface WebReferenceItem {
  text: string;
  sourceRefs: string[];
}

export interface CategoryWebReference extends WebReferenceItem {
  categoryId: string;
}

export interface WebSource {
  webId: string;
  title: string;
  url: string;
  source: string;
  sourceHint: string;
  publishedAt: string;
}

export interface WebContext {
  candidateCount: number;
  usedSourceCount: number;
  eventBackground: WebReferenceItem[];
  corroborations: CategoryWebReference[];
  counterSignals: CategoryWebReference[];
  sources: WebSource[];
  sourceLimitations: string[];
}

export interface Dashboard {
  runId: string;
  title: string;
  researchQuestion: string;
  generatedAt: string;
  platforms: PlatformStat[];
  counts: {
    inputRelevance: number;
    foldedRecords: number;
    representedComments: number;
    finalAnalyzed: number;
  };
  overallSentiment: unknown;
  categoriesNonExclusive: boolean;
  categories: CategoryStat[];
  methodology: {
    weighting: string;
    categoryScope: string;
    overallSentimentScope: string;
    limitations: string[];
  };
  webContext: WebContext | null;
  analysisSummary: AnalysisSummary | null;
  commentDrilldownAvailable: boolean;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const textValue = (value: unknown, fallback = "") =>
  typeof value === "string" && value.trim() ? value.trim() : fallback;

const numberValue = (value: unknown) => {
  const converted = typeof value === "number" ? value : Number(value);
  return Number.isFinite(converted) && converted >= 0 ? converted : 0;
};

const platformName = (value: unknown) => {
  if (typeof value === "string") return value.trim();
  return isRecord(value) ? textValue(value.platform) : "";
};

export const platformLabel = (platform: string) => ({
  bilibili: "Bilibili",
  douyin: "抖音",
  xiaohongshu: "小红书",
})[platform.toLowerCase()] || platform;

export function normalizeRunSummary(value: unknown, index: number): RunSummary {
  const source = isRecord(value) ? value : {};
  const rawStatus = textValue(source.status);
  const status = rawStatus === "ready" ? "ready" : "error";
  const rawPlatforms = Array.isArray(source.platforms) ? source.platforms : [];
  return {
    runId: textValue(source.run_id, `unknown-${index}`),
    title: textValue(source.research_title, textValue(source.research_target, "未命名调查")),
    generatedAt: textValue(source.generated_at),
    platforms: rawPlatforms.map(platformName).filter(Boolean),
    finalCount: numberValue(source.final_analyzed_count),
    categoryCount: numberValue(source.category_count),
    status,
    error: textValue(source.error) || undefined,
  };
}

export function filterAndSortRuns(items: RunSummary[], query: string, order: SortOrder) {
  const normalizedQuery = query.trim().toLocaleLowerCase();
  return items
    .filter((item) => item.title.toLocaleLowerCase().includes(normalizedQuery))
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      const aTime = Date.parse(a.item.generatedAt) || 0;
      const bTime = Date.parse(b.item.generatedAt) || 0;
      const difference = order === "newest" ? bTime - aTime : aTime - bTime;
      return difference || a.index - b.index;
    })
    .map(({ item }) => item);
}

export function runListState({
  runCount,
  visibleCount,
  loading,
  error,
}: {
  runCount: number;
  visibleCount: number;
  loading: boolean;
  error: string;
}): RunListState {
  if (loading && runCount === 0) return "loading";
  if (error && runCount === 0) return "error";
  if (visibleCount > 0) return "results";
  return runCount > 0 ? "no-matches" : "empty";
}

const normalizeComment = (value: unknown, index: number): RepresentativeComment => {
  const source = isRecord(value) ? value : {};
  return {
    recordId: textValue(source.record_id, `未知记录-${index + 1}`),
    platform: textValue(source.platform, "未知平台"),
    text: textValue(source.text, "原文缺失"),
    supportCount: numberValue(source.support_count),
  };
};

const stringArray = (value: unknown) => Array.isArray(value)
  ? value.map((item) => textValue(item)).filter(Boolean)
  : [];

const riskLevel = (value: unknown): RiskLevel | null =>
  value === "low" || value === "middle" || value === "high" ? value : null;

function normalizeAnalysisSummary(value: unknown): AnalysisSummary | null {
  const source = isRecord(value) ? value : {};
  if (source.schema_version !== "game-ops-final-summary-1.0") return null;
  const risk = isRecord(source.risk) ? source.risk : {};
  const confidence = isRecord(source.confidence) ? source.confidence : {};
  const riskLevelValue = riskLevel(risk.level);
  const confidenceLevel = riskLevel(confidence.level);
  const researchTitle = textValue(source.research_title);
  const coreJudgment = textValue(source.core_judgment);
  if (!riskLevelValue || !confidenceLevel || !researchTitle || !coreJudgment) return null;
  return {
    schemaVersion: String(source.schema_version),
    researchTitle,
    coreJudgment,
    risk: {
      score: Math.min(1, numberValue(risk.score)),
      level: riskLevelValue,
      rationale: textValue(risk.rationale),
    },
    confidence: { level: confidenceLevel, rationale: textValue(confidence.rationale) },
    keyFindings: stringArray(source.key_findings),
    operationDirections: stringArray(source.operation_directions),
    evidenceRefs: stringArray(source.evidence_refs),
    evidenceGaps: stringArray(source.evidence_gaps),
  };
}

export function normalizeCategoryCommentResult(value: unknown): CategoryCommentResult {
  const source = isRecord(value) ? value : {};
  const rawSentiment = textValue(source.sentiment);
  const sentiment: SentimentKey = ["positive", "negative", "neutral", "mixed"].includes(rawSentiment)
    ? rawSentiment as SentimentKey
    : "neutral";
  return {
    categoryId: textValue(source.category_id),
    sentiment,
    weightedExpressionCount: numberValue(source.weighted_expression_count),
    representativeRecordCount: numberValue(source.representative_record_count),
    records: Array.isArray(source.records) ? source.records.map(normalizeComment) : [],
  };
}

const normalizeSourceRefs = (value: unknown) => Array.isArray(value)
  ? value.map((item) => textValue(item)).filter(Boolean)
  : [];

const normalizeWebReference = (value: unknown): WebReferenceItem | null => {
  const source = isRecord(value) ? value : {};
  const text = textValue(source.text);
  const sourceRefs = normalizeSourceRefs(source.source_refs);
  return text && sourceRefs.length ? { text, sourceRefs } : null;
};

const normalizeCategoryWebReference = (value: unknown): CategoryWebReference | null => {
  const source = isRecord(value) ? value : {};
  const normalized = normalizeWebReference(source);
  const categoryId = textValue(source.dashboard_category_id);
  return normalized && categoryId ? { ...normalized, categoryId } : null;
};

function normalizeWebContext(value: unknown): WebContext | null {
  const source = isRecord(value) ? value : {};
  const sources = Array.isArray(source.sources) ? source.sources.map((value) => {
    const item = isRecord(value) ? value : {};
    return {
      webId: textValue(item.web_id ?? item.id),
      title: textValue(item.title, "未命名来源"),
      url: textValue(item.url),
      source: textValue(item.source ?? item.kind, "来源未知"),
      sourceHint: textValue(item.source_hint ?? item.kind, "other"),
      publishedAt: textValue(item.published_at),
    };
  }).filter((item) => item.webId && item.url) : [];
  const status = textValue(source.status);
  const legacyEnriched = !status && sources.length > 0;
  const usedSourceCount = source.used_source_count === undefined
    ? sources.length
    : numberValue(source.used_source_count);
  if ((status !== "enriched" && !legacyEnriched) || usedSourceCount === 0 || !sources.length) return null;
  return {
    candidateCount: source.candidate_count === undefined
      ? sources.length
      : numberValue(source.candidate_count),
    usedSourceCount,
    eventBackground: (Array.isArray(source.event_background) ? source.event_background : [])
      .map(normalizeWebReference)
      .filter((item): item is WebReferenceItem => item !== null)
      .slice(0, 4),
    corroborations: (Array.isArray(source.corroborations) ? source.corroborations : [])
      .map(normalizeCategoryWebReference)
      .filter((item): item is CategoryWebReference => item !== null),
    counterSignals: (Array.isArray(source.counter_signals) ? source.counter_signals : [])
      .map(normalizeCategoryWebReference)
      .filter((item): item is CategoryWebReference => item !== null),
    sources,
    sourceLimitations: Array.isArray(source.source_limitations)
      ? source.source_limitations.map((item) => textValue(item)).filter(Boolean)
      : [],
  };
}

export function webItemsForCategory(webContext: WebContext | null, categoryId: string) {
  return {
    corroboration: webContext?.corroborations.find((item) => item.categoryId === categoryId) ?? null,
    counterSignal: webContext?.counterSignals.find((item) => item.categoryId === categoryId) ?? null,
  };
}

export function sortCategories(values: unknown): CategoryStat[] {
  if (!Array.isArray(values)) return [];
  const categories = values
    .map((value, index) => {
      const source = isRecord(value) ? value : {};
      const comments = Array.isArray(source.representative_comments)
        ? source.representative_comments.slice(0, 2).map(normalizeComment)
        : [];
      return {
        index,
        category: {
          id: textValue(source.category_id, `category-${index + 1}`),
          name: textValue(source.name, `未命名类别 ${index + 1}`),
          count: numberValue(source.count),
          ratio: numberValue(source.ratio_of_final_analyzed),
          summary: textValue(source.summary, "暂无类别摘要。"),
          sentiment: isRecord(source.sentiment) ? source.sentiment : {},
          comments,
        },
      };
    })
    .map(({ category }) => category);
  return sortCategoryStats(categories, "volume");
}

export function categoryNegativeCount(category: CategoryStat) {
  return sentimentEntries(category.sentiment).find((item) => item.key === "negative")?.count ?? 0;
}

export function sortCategoryStats(categories: CategoryStat[], order: CategorySortOrder) {
  return categories
    .map((category, index) => ({ category, index }))
    .sort((a, b) => {
      const difference = order === "negative"
        ? categoryNegativeCount(b.category) - categoryNegativeCount(a.category)
        : b.category.count - a.category.count;
      return difference || a.index - b.index;
    })
    .map(({ category }) => category);
}

export function normalizeDashboard(value: unknown): Dashboard {
  const source = isRecord(value) ? value : {};
  const counts = isRecord(source.counts) ? source.counts : {};
  const methodology = isRecord(source.methodology) ? source.methodology : {};
  const rawPlatforms = Array.isArray(source.platforms) ? source.platforms : [];
  const analysisSummary = normalizeAnalysisSummary(source.analysis_summary);
  const researchQuestion = textValue(source.research_target, "未命名调查");
  return {
    runId: textValue(source.run_id, "unknown"),
    title: analysisSummary?.researchTitle || researchQuestion,
    researchQuestion,
    generatedAt: textValue(source.generated_at),
    platforms: rawPlatforms.map((value) => {
      const item: Record<string, unknown> = isRecord(value) ? value : { platform: value };
      return {
        platform: textValue(item.platform, "未知平台"),
        relevanceCount: numberValue(item.relevance_count),
        foldedCount: numberValue(item.folded_count),
        includedCount: numberValue(item.included_represented_count ?? item.represented_count),
      };
    }),
    counts: {
      inputRelevance: numberValue(counts.input_relevance_count),
      foldedRecords: numberValue(counts.folded_record_count),
      representedComments: numberValue(counts.represented_comment_count),
      finalAnalyzed: numberValue(counts.final_analyzed_count ?? source.final_analyzed_count),
    },
    overallSentiment: isRecord(source.overall_sentiment) ? source.overall_sentiment : {},
    categoriesNonExclusive: source.category_statistics_non_exclusive !== false,
    categories: sortCategories(source.categories),
    methodology: {
      weighting: textValue(methodology.weighting, "暂无加权方法说明。"),
      categoryScope: textValue(methodology.category_scope, "暂无类别口径说明。"),
      overallSentimentScope: textValue(methodology.overall_sentiment_scope, "暂无总体情绪口径说明。"),
      limitations: Array.isArray(methodology.limitations)
        ? methodology.limitations.map((item) => textValue(item)).filter(Boolean)
        : [],
    },
    webContext: normalizeWebContext(source.web_context),
    analysisSummary,
    commentDrilldownAvailable: source.comment_drilldown_available === true,
  };
}

const sentimentMeta: Array<Pick<SentimentItem, "key" | "label" | "color">> = [
  { key: "positive", label: "正向", color: "var(--sentiment-positive)" },
  { key: "negative", label: "负向", color: "var(--sentiment-negative)" },
  { key: "neutral", label: "中性", color: "var(--sentiment-neutral)" },
  { key: "mixed", label: "混合", color: "var(--sentiment-mixed)" },
];

export function sentimentEntries(value: unknown): SentimentItem[] {
  const source = isRecord(value) ? value : {};
  const entries = sentimentMeta.map((meta) => {
    const rawItem = source[meta.key];
    const item: Record<string, unknown> = isRecord(rawItem) ? rawItem : {};
    const rawRatio = item.ratio;
    return {
      ...meta,
      count: numberValue(item.count),
      ratio: numberValue(rawRatio),
      hasValidRatio: typeof rawRatio === "number" && Number.isFinite(rawRatio) && rawRatio >= 0 && rawRatio <= 1,
    };
  });
  const ratioSum = entries.reduce((sum, item) => sum + item.ratio, 0);
  const countSum = entries.reduce((sum, item) => sum + item.count, 0);
  const countRatiosMatch = countSum > 0 && entries.every(
    (item) => Math.abs(item.ratio - item.count / countSum) <= 0.015,
  );
  const useCounts = countSum > 0 && (
    entries.some((item) => !item.hasValidRatio)
    || ratioSum < 0.98
    || ratioSum > 1.02
    || !countRatiosMatch
  );
  return entries.map(({ hasValidRatio: _hasValidRatio, ...item }) => ({
    ...item,
    ratio: useCounts && countSum > 0 ? item.count / countSum : item.ratio,
  }));
}

export function formatDate(value: string) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "日期未知";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatInteger(value: number) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(numberValue(value));
}

export function formatPercent(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(numberValue(value));
}
