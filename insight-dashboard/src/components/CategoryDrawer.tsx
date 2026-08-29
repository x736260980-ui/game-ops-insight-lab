import { useEffect, useRef, useState } from "react";
import { fetchCategoryComments } from "../api";
import { formatInteger, formatPercent, normalizeCategoryCommentResult, platformLabel, sentimentEntries, webItemsForCategory, type CategoryCommentResult, type CategoryStat, type SentimentKey, type WebContext } from "../lib/dashboard";
import { SourceLinks } from "./WebContextPanel";

interface CategoryDrawerProps {
  runId: string;
  category: CategoryStat;
  webContext: WebContext | null;
  drilldownAvailable: boolean;
  onClose: () => void;
}

export function CategoryDrawer({ runId, category, webContext, drilldownAvailable, onClose }: CategoryDrawerProps) {
  const drawerRef = useRef<HTMLElement>(null);
  const [drilldown, setDrilldown] = useState<CategoryCommentResult | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [drilldownError, setDrilldownError] = useState("");
  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const background = drawerRef.current?.parentElement?.parentElement;
    const siblings = background ? Array.from(background.children).filter((element) => !element.classList.contains("drawer-layer")) as HTMLElement[] : [];
    siblings.forEach((element) => { element.inert = true; });
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    drawerRef.current?.querySelector<HTMLElement>("button")?.focus();

    const manageKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") return onClose();
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = Array.from(drawerRef.current.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter((element) => !element.hasAttribute("disabled"));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", manageKeyboard);
    return () => {
      document.removeEventListener("keydown", manageKeyboard);
      siblings.forEach((element) => { element.inert = false; });
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [onClose]);

  const sentiment = sentimentEntries(category.sentiment);
  const webItems = webItemsForCategory(webContext, category.id);
  const hasWebItems = Boolean(webItems.corroboration || webItems.counterSignal);
  const loadSentiment = (sentimentKey: SentimentKey) => {
    if (!drilldownAvailable) return;
    setDrilldownLoading(true);
    setDrilldownError("");
    fetchCategoryComments(runId, category.id, sentimentKey)
      .then((value) => setDrilldown(normalizeCategoryCommentResult(value)))
      .catch((error) => setDrilldownError(error instanceof Error ? error.message : "评论明细读取失败。"))
      .finally(() => setDrilldownLoading(false));
  };
  return (
    <div className="drawer-layer" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
        <header className="drawer-header">
          <div><p className="section-kicker">类别证据</p><h2 id="drawer-title">{category.name}</h2></div>
          <button className="icon-button" onClick={onClose} aria-label="关闭详情抽屉">×</button>
        </header>
        <div className="drawer-body">
          <div className="drawer-metrics">
            <div><span>类别数量</span><strong>{formatInteger(category.count)}</strong></div>
            <div><span>占最终分析</span><strong>{formatPercent(category.ratio)}</strong></div>
          </div>
          <section>
            <h3>洞察摘要</h3>
            <p className="drawer-summary">{category.summary}</p>
          </section>
          <section>
            <h3>分类内情绪</h3>
            <div className="drawer-sentiments">
              {sentiment.map((item) => (
                <button key={item.key} type="button" disabled={!drilldownAvailable || item.count === 0 || drilldownLoading} onClick={() => loadSentiment(item.key)}>
                  <span className="legend-dot" style={{ background: item.color }} /><span>{item.label}</span><strong>{formatInteger(item.count)}</strong><small>{formatPercent(item.ratio)}</small>
                </button>
              ))}
            </div>
            {!drilldownAvailable && <p className="drilldown-note">该调查未保留可回查的分类评论明细。</p>}
          </section>
          <section>
            <div className="evidence-heading"><h3>代表评论</h3><span>最多 2 条</span></div>
            {category.comments.length ? category.comments.map((comment) => (
              <blockquote className="comment-card" key={`${comment.platform}-${comment.recordId}`}>
                <div className="comment-meta">
                  <span className="tag">{platformLabel(comment.platform)}</span>
                  <code>{comment.recordId}</code>
                  <span className="support-count">代表 {formatInteger(comment.supportCount)} 条相似表达</span>
                </div>
                <p>{comment.text}</p>
              </blockquote>
            )) : <div className="inline-empty">该类别没有提供代表评论。</div>}
          </section>
          {(drilldownLoading || drilldownError || drilldown) && (
            <section className="drilldown-results">
              <div className="evidence-heading"><h3>{drilldown ? `${sentiment.find((item) => item.key === drilldown.sentiment)?.label || "分类"}评论` : "评论明细"}</h3><span>{drilldownLoading ? "正在读取…" : "折叠代表记录"}</span></div>
              {drilldownError && <div className="inline-empty">{drilldownError}</div>}
              {drilldown && <>
                <div className="drilldown-counts"><div><span>相似表达数</span><strong>{formatInteger(drilldown.weightedExpressionCount)}</strong></div><div><span>折叠代表记录</span><strong>{formatInteger(drilldown.representativeRecordCount)}</strong></div></div>
                {drilldown.records.map((comment) => (
                  <blockquote className="comment-card" key={`${comment.platform}-${comment.recordId}`}>
                    <div className="comment-meta"><span className="tag">{platformLabel(comment.platform)}</span><code>{comment.recordId}</code><span className="support-count">代表 {formatInteger(comment.supportCount)} 条相似表达</span></div>
                    <p>{comment.text}</p>
                  </blockquote>
                ))}
              </>}
            </section>
          )}
          {hasWebItems && webContext && (
            <section>
              <div className="evidence-heading"><h3>外部参考</h3><span>不计入评论统计</span></div>
              <div className="category-web-items">
                {webItems.corroboration && (
                  <article className="category-web-item">
                    <strong>跨来源补充</strong>
                    <p>{webItems.corroboration.text}</p>
                    <SourceLinks refs={webItems.corroboration.sourceRefs} sources={webContext.sources} />
                  </article>
                )}
                {webItems.counterSignal && (
                  <article className="category-web-item counter-signal">
                    <strong>不同声音</strong>
                    <p>{webItems.counterSignal.text}</p>
                    <SourceLinks refs={webItems.counterSignal.sourceRefs} sources={webContext.sources} />
                  </article>
                )}
              </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
