import { useMemo, useState } from "react";
import {
  filterAndSortRuns,
  formatDate,
  formatInteger,
  platformLabel,
  runListState,
  type RunSummary,
  type SortOrder,
} from "../lib/dashboard";

interface RunListProps {
  runs: RunSummary[];
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onOpen: (run: RunSummary) => void;
}

function SearchIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></svg>;
}

export function RunList({ runs, loading, error, onRefresh, onOpen }: RunListProps) {
  const [query, setQuery] = useState("");
  const [order, setOrder] = useState<SortOrder>("newest");
  const visibleRuns = useMemo(() => filterAndSortRuns(runs, query, order), [runs, query, order]);
  const state = runListState({ runCount: runs.length, visibleCount: visibleRuns.length, loading, error });

  return (
    <main className="shell list-page">
      <header className="masthead">
        <div className="brand-mark" aria-hidden="true">GI</div>
        <div>
          <p className="eyebrow">GAME RESEARCH ARCHIVE</p>
          <h1>玩家洞察档案</h1>
          <p className="masthead-copy">从公开评论中整理可复核的讨论结构、情绪与原始证据。</p>
        </div>
      </header>

      <section className="archive-section" aria-labelledby="archive-title">
        <div className="section-heading archive-heading">
          <div>
            <p className="section-kicker">历史调查</p>
            <h2 id="archive-title">研究记录</h2>
          </div>
          <div className="archive-count"><strong>{runs.length}</strong><span>份调查</span></div>
        </div>

        <div className="toolbar">
          <label className="search-field">
            <span className="sr-only">搜索调查标题</span>
            <SearchIcon />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索研究主题…" />
          </label>
          <label className="select-field">
            <span className="sr-only">调查排序</span>
            <select value={order} onChange={(event) => setOrder(event.target.value as SortOrder)}>
              <option value="newest">最新优先</option>
              <option value="oldest">最早优先</option>
            </select>
          </label>
          <button className="button button-secondary" onClick={onRefresh} disabled={loading}>
            <span className={loading ? "refresh-icon is-spinning" : "refresh-icon"} aria-hidden="true">↻</span>
            刷新
          </button>
        </div>

        {error && (
          <div className="notice notice-error" role="alert">
            <div><strong>暂时无法读取调查列表</strong><p>{error}</p></div>
            <button className="text-button" onClick={onRefresh}>重试</button>
          </div>
        )}

        {state === "loading" ? (
          <div className="card-grid" aria-label="正在加载调查">
            {[0, 1, 2].map((item) => <div className="run-card skeleton" key={item} />)}
          </div>
        ) : state === "results" ? (
          <div className="card-grid">
            {visibleRuns.map((run) => {
              const broken = run.status === "error";
              return (
                <article className={broken ? "run-card run-card-error" : "run-card"} key={run.runId}>
                  <div className="run-card-top">
                    <span className={broken ? "status-dot status-error" : "status-dot"} />
                    <span>{broken ? "文件异常" : "分析完成"}</span>
                    <time>{formatDate(run.generatedAt)}</time>
                  </div>
                  <h3>{run.title}</h3>
                  {broken ? (
                    <p className="run-error-copy">{run.error || "该调查数据无法解析，其他调查仍可正常查看。"}</p>
                  ) : (
                    <>
                      <div className="tag-row">
                        {run.platforms.length ? run.platforms.map((platform) => <span className="tag" key={platform}>{platformLabel(platform)}</span>) : <span className="tag tag-muted">平台未知</span>}
                      </div>
                      <dl className="run-stats">
                        <div><dt>最终纳入</dt><dd>{formatInteger(run.finalCount)}</dd></div>
                        <div><dt>动态类别</dt><dd>{formatInteger(run.categoryCount)}</dd></div>
                      </dl>
                    </>
                  )}
                  <button className="card-link" onClick={() => onOpen(run)} disabled={broken}>
                    {broken ? "不可打开" : "查看完整洞察"}<span aria-hidden="true">→</span>
                  </button>
                </article>
              );
            })}
          </div>
        ) : state !== "error" && (
          <div className="empty-state">
            <div className="empty-glyph" aria-hidden="true">⌕</div>
            <h3>{state === "no-matches" ? "没有匹配的调查" : "还没有调查记录"}</h3>
            <p>{state === "no-matches" ? "尝试缩短关键词或清空搜索条件。" : "当后台生成 dashboard.json 后，调查会出现在这里。"}</p>
            {query && <button className="button button-secondary" onClick={() => setQuery("")}>清空搜索</button>}
          </div>
        )}
      </section>
    </main>
  );
}
