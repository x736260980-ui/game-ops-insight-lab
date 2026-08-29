import { useMemo, useState } from "react";
import {
  categoryNegativeCount,
  formatDate,
  formatInteger,
  formatPercent,
  sortCategoryStats,
  platformLabel,
  type CategorySortOrder,
  type CategoryStat,
  type Dashboard,
} from "../lib/dashboard";
import { CategoryDrawer } from "./CategoryDrawer";
import { SentimentDonut } from "./SentimentDonut";
import { WebContextPanel } from "./WebContextPanel";

interface DashboardDetailProps {
  dashboard: Dashboard;
  onBack: () => void;
}

function ComparisonBar({ value, max }: { value: number; max: number }) {
  const width = max > 0 ? Math.max(2, value / max * 100) : 0;
  return <span className="comparison-track"><span style={{ width: `${width}%` }} /></span>;
}

export function DashboardDetail({ dashboard, onBack }: DashboardDetailProps) {
  const [selectedCategory, setSelectedCategory] = useState<CategoryStat | null>(null);
  const [categorySort, setCategorySort] = useState<CategorySortOrder>("volume");
  const sortedCategories = useMemo(
    () => sortCategoryStats(dashboard.categories, categorySort),
    [dashboard.categories, categorySort],
  );
  const maxPlatformCount = Math.max(0, ...dashboard.platforms.flatMap((item) => [item.relevanceCount, item.foldedCount, item.includedCount]));
  const kpis = [
    { label: "初筛相关", value: dashboard.counts.inputRelevance, note: "进入相关性筛选" },
    { label: "折叠记录", value: dashboard.counts.foldedRecords, note: "合并同质表达后" },
    { label: "代表评论", value: dashboard.counts.representedComments, note: "按 support_count 加权" },
    { label: "最终纳入", value: dashboard.counts.finalAnalyzed, note: "进入本次洞察" },
  ];

  return (
    <main className="detail-page">
      <header className="detail-nav shell">
        <button className="back-button" onClick={onBack}><span aria-hidden="true">←</span>返回调查列表</button>
        <div className="brand-inline"><span>GI</span><strong>玩家洞察档案</strong></div>
      </header>

      <section className="detail-hero">
        <div className="shell">
          <div className="hero-meta">
            <span className="status-label"><i />分析完成</span>
            <time>{formatDate(dashboard.generatedAt)}</time>
            <span>研究编号 {dashboard.runId}</span>
          </div>
          <h1>{dashboard.title}</h1>
          {dashboard.researchQuestion !== dashboard.title && <p className="research-question"><strong>研究问题</strong>{dashboard.researchQuestion}</p>}
          <div className="hero-bottom">
            <div className="tag-row">
              {dashboard.platforms.length ? dashboard.platforms.map((item) => <span className="tag tag-hero" key={item.platform}>{platformLabel(item.platform)}</span>) : <span className="tag tag-hero">平台未知</span>}
            </div>
            <p className="sample-warning"><span aria-hidden="true">ⓘ</span>样本来自公开平台评论，是有偏观察，不代表全体玩家。</p>
          </div>
        </div>
      </section>

      <div className="shell detail-content">
        {dashboard.analysisSummary && (
          <section className="insight-section" aria-labelledby="insight-title">
            <div className="section-heading"><div><p className="section-kicker">FINAL ASSESSMENT</p><h2 id="insight-title">运营判断</h2></div></div>
            <div className="insight-grid">
              <article className="panel insight-core">
                <h3>核心判断</h3>
                <p>{dashboard.analysisSummary.coreJudgment}</p>
                {dashboard.analysisSummary.keyFindings.length > 0 && <ul>{dashboard.analysisSummary.keyFindings.map((item, index) => <li key={index}>{item}</li>)}</ul>}
              </article>
              <article className="panel risk-card">
                <span>综合运营风险</span>
                <strong>{dashboard.analysisSummary.risk.score.toFixed(1)}</strong>
                <em className={`risk-level risk-${dashboard.analysisSummary.risk.level}`}>{dashboard.analysisSummary.risk.level}</em>
                <p>{dashboard.analysisSummary.risk.rationale}</p>
                <small>置信度 {dashboard.analysisSummary.confidence.level} · {dashboard.analysisSummary.confidence.rationale}</small>
              </article>
            </div>
            <div className="direction-grid">
              {dashboard.analysisSummary.operationDirections.map((item, index) => <article key={index}><span>方向 {String(index + 1).padStart(2, "0")}</span><p>{item}</p></article>)}
            </div>
          </section>
        )}
        <section aria-labelledby="flow-title">
          <div className="section-heading"><div><p className="section-kicker">ANALYSIS FLOW</p><h2 id="flow-title">分析流程</h2></div></div>
          <div className="kpi-grid">
            {kpis.map((kpi, index) => (
              <article className="kpi-card" key={kpi.label}>
                <span className="kpi-index">0{index + 1}</span>
                <p>{kpi.label}</p><strong>{formatInteger(kpi.value)}</strong><small>{kpi.note}</small>
              </article>
            ))}
          </div>
        </section>

        {dashboard.webContext && <WebContextPanel context={dashboard.webContext} />}

        <section className="two-column analytics-row">
          <article className="panel" aria-labelledby="platform-title">
            <div className="panel-heading"><div><p className="section-kicker">PLATFORM</p><h2 id="platform-title">平台样本对比</h2></div><span className="panel-note">评论数</span></div>
            {dashboard.platforms.length ? (
              <div className="platform-comparison">
                <div className="comparison-head"><span>平台</span><span>相关</span><span>折叠</span><span>最终纳入</span></div>
                {dashboard.platforms.map((platform) => (
                  <div className="comparison-row" key={platform.platform}>
                    <strong>{platformLabel(platform.platform)}</strong>
                    {[platform.relevanceCount, platform.foldedCount, platform.includedCount].map((value, index) => (
                      <div className="bar-value" key={index}><ComparisonBar value={value} max={maxPlatformCount} /><span>{formatInteger(value)}</span></div>
                    ))}
                  </div>
                ))}
              </div>
            ) : <div className="inline-empty">该调查没有提供平台分布数据。</div>}
          </article>

          <article className="panel" aria-labelledby="sentiment-title">
            <div className="panel-heading"><div><p className="section-kicker">SENTIMENT</p><h2 id="sentiment-title">总体情绪</h2></div><span className="panel-note">互斥口径</span></div>
            <SentimentDonut value={dashboard.overallSentiment} />
          </article>
        </section>

        <section aria-labelledby="category-title">
          <div className="section-heading category-heading">
            <div><p className="section-kicker">DYNAMIC CATEGORIES</p><h2 id="category-title">玩家讨论类别</h2></div>
            <div className="category-heading-tools">
              <p><span aria-hidden="true">ⓘ</span>{dashboard.categoriesNonExclusive ? "类别为多选、互不排斥；数量和占比之和可能超过最终评论量或 100%。" : "类别采用互斥口径，每条评论仅计入一个类别。"}</p>
              <label className="category-sort-field">
                <span>排序</span>
                <select value={categorySort} onChange={(event) => setCategorySort(event.target.value as CategorySortOrder)}>
                  <option value="volume">讨论量</option>
                  <option value="negative">负面反馈量</option>
                </select>
              </label>
            </div>
          </div>
          {dashboard.categories.length ? (
            <div className="category-list">
              {sortedCategories.map((category, index) => (
                <button className="category-card" key={category.id} onClick={() => setSelectedCategory(category)}>
                  <span className="category-rank">{String(index + 1).padStart(2, "0")}</span>
                  <div className="category-main">
                    <div className="category-title-row"><h3>{category.name}</h3><span>查看证据 →</span></div>
                    <p>{category.summary}</p>
                    <SentimentDonut value={category.sentiment} compact />
                  </div>
                  <div className="category-number">
                    <strong>{formatInteger(categorySort === "negative" ? categoryNegativeCount(category) : category.count)}</strong>
                    <span>{categorySort === "negative" ? `负向 / 共 ${formatInteger(category.count)}` : `${formatPercent(category.ratio)} / 最终`}</span>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="empty-state compact-empty"><div className="empty-glyph" aria-hidden="true">—</div><h3>暂无讨论类别</h3><p>该调查没有输出动态类别统计。</p></div>
          )}
        </section>

        <section className="method-section">
          <details>
            <summary><span><small>METHOD & LIMITATIONS</small><strong>方法与限制</strong></span><i aria-hidden="true">＋</i></summary>
            <div className="method-content">
              <div><h3>数量加权</h3><p>{dashboard.methodology.weighting}</p></div>
              <div><h3>类别口径</h3><p>{dashboard.methodology.categoryScope}</p></div>
              <div><h3>情绪口径</h3><p>{dashboard.methodology.overallSentimentScope}</p></div>
              <div><h3>研究限制</h3>{dashboard.methodology.limitations.length ? <ul>{dashboard.methodology.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>暂无补充限制说明。</p>}</div>
              {dashboard.analysisSummary && <div><h3>分析复核</h3><p>最终结论经过双模型独立分析、交叉讨论与统一复核。</p></div>}
              {dashboard.webContext && <div><h3>网页资料边界</h3>{dashboard.webContext.sourceLimitations.length ? <ul>{dashboard.webContext.sourceLimitations.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>网页资料仅用于背景和定性参考，不参与评论统计。</p>}</div>}
            </div>
          </details>
        </section>
      </div>

      <footer><div className="shell"><span>Game Insight Archive</span><p>公开评论研究 · 结论需结合产品与业务语境判断</p></div></footer>
      {selectedCategory && <CategoryDrawer runId={dashboard.runId} category={selectedCategory} webContext={dashboard.webContext} drilldownAvailable={dashboard.commentDrilldownAvailable} onClose={() => setSelectedCategory(null)} />}
    </main>
  );
}
