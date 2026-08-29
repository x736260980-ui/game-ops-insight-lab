import { formatInteger, formatPercent, sentimentEntries } from "../lib/dashboard";

interface SentimentDonutProps {
  value: unknown;
  compact?: boolean;
}

export function SentimentDonut({ value, compact = false }: SentimentDonutProps) {
  const items = sentimentEntries(value);
  const total = items.reduce((sum, item) => sum + item.count, 0);
  let offset = 0;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;

  if (compact) {
    return (
      <div className="sentiment-strip" aria-label="分类内情绪构成">
        {items.map((item) => <span key={item.key} style={{ width: `${Math.max(0, item.ratio * 100)}%`, background: item.color }} title={`${item.label} ${formatPercent(item.ratio)}`} />)}
      </div>
    );
  }

  return (
    <div className="sentiment-layout">
      <div className="donut-wrap">
        <svg className="donut" viewBox="0 0 110 110" role="img" aria-label={`总体情绪，共 ${formatInteger(total)} 条`}>
          <circle className="donut-track" cx="55" cy="55" r={radius} />
          {items.map((item) => {
            const length = Math.min(circumference, item.ratio * circumference);
            const element = (
              <circle
                className="donut-segment"
                cx="55"
                cy="55"
                r={radius}
                key={item.key}
                stroke={item.color}
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
              />
            );
            offset += length;
            return element;
          })}
        </svg>
        <div className="donut-center"><strong>{formatInteger(total)}</strong><span>评论</span></div>
      </div>
      <div className="sentiment-legend">
        {items.map((item) => (
          <div className="legend-row" key={item.key}>
            <span className="legend-dot" style={{ background: item.color }} />
            <span>{item.label}</span>
            <strong>{formatInteger(item.count)}</strong>
            <small>{formatPercent(item.ratio)}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
