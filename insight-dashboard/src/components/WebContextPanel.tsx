import { formatDate, formatInteger, type WebContext, type WebSource } from "../lib/dashboard";

const sourceHintLabel = (value: string) => ({
  official: "官方",
  taptap: "TapTap",
  nga: "NGA",
  media: "媒体",
  review: "测评",
  other: "其他",
})[value.toLowerCase()] || value;

export function SourceLinks({ refs, sources }: { refs: string[]; sources: WebSource[] }) {
  const sourceMap = new Map(sources.map((source) => [source.webId, source]));
  return (
    <span className="source-links">
      {refs.map((ref) => {
        const source = sourceMap.get(ref);
        return source ? (
          <a key={ref} href={source.url} target="_blank" rel="noreferrer" title={source.title}>
            {ref} · {sourceHintLabel(source.sourceHint)}
          </a>
        ) : null;
      })}
    </span>
  );
}

export function WebContextPanel({ context }: { context: WebContext }) {
  return (
    <section aria-labelledby="web-context-title">
      <div className="section-heading web-context-heading">
        <div>
          <p className="section-kicker">WEB CONTEXT</p>
          <h2 id="web-context-title">事件背景与外部参考</h2>
        </div>
        <p><span aria-hidden="true">ⓘ</span>网页资料仅作背景和定性参考，不计入评论样本。</p>
      </div>

      <div className="web-context-card">
        <div className="background-column">
          <h3>事件背景</h3>
          {context.eventBackground.length ? (
            <ol className="background-list">
              {context.eventBackground.map((item, index) => (
                <li key={`${item.sourceRefs.join("-")}-${index}`}>
                  <span className="background-index">{String(index + 1).padStart(2, "0")}</span>
                  <div><p>{item.text}</p><SourceLinks refs={item.sourceRefs} sources={context.sources} /></div>
                </li>
              ))}
            </ol>
          ) : <div className="inline-empty">本次没有单独采用事件背景条目。</div>}
        </div>

        <aside className="web-context-summary">
          <p>网页资料筛选</p>
          <div className="web-counts">
            <div><strong>{formatInteger(context.candidateCount)}</strong><span>候选结果</span></div>
            <div><strong>{formatInteger(context.usedSourceCount)}</strong><span>实际采用</span></div>
          </div>
          <small>采用来源只用于解释事件、提供跨社区补充或保留不同声音。</small>
        </aside>
      </div>

      <details className="web-source-details">
        <summary>查看已采用来源 <span>{formatInteger(context.sources.length)} 条</span></summary>
        <div className="web-source-list">
          {context.sources.map((source) => (
            <a key={source.webId} href={source.url} target="_blank" rel="noreferrer">
              <span className="source-id">{source.webId}</span>
              <span className="source-copy"><strong>{source.title}</strong><small>{source.source} · {sourceHintLabel(source.sourceHint)}{source.publishedAt ? ` · ${formatDate(source.publishedAt)}` : ""}</small></span>
              <span aria-hidden="true">↗</span>
            </a>
          ))}
        </div>
      </details>
    </section>
  );
}
