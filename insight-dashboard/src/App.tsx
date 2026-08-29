import { useCallback, useEffect, useRef, useState } from "react";
import { fetchRun, fetchRuns } from "./api";
import { DashboardDetail } from "./components/DashboardDetail";
import { RunList } from "./components/RunList";
import { normalizeDashboard, normalizeRunSummary, type Dashboard, type RunSummary } from "./lib/dashboard";

type SelectedRun = { id: string; dashboard?: Dashboard; loading: boolean; error: string };

function errorMessage(error: unknown) {
  if (error instanceof DOMException && error.name === "AbortError") return "";
  return error instanceof Error ? error.message : "发生未知错误，请稍后重试。";
}

export default function App() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [selected, setSelected] = useState<SelectedRun | null>(null);
  const detailController = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true);
    setListError("");
    fetchRuns(controller.signal)
      .then((items) => setRuns(items.map(normalizeRunSummary)))
      .catch((error) => {
        const message = errorMessage(error);
        if (message) setListError(message);
      })
      .finally(() => !controller.signal.aborted && setListLoading(false));
    return () => controller.abort();
  }, [refreshKey]);

  useEffect(() => () => detailController.current?.abort(), []);

  const loadDetail = useCallback((run: RunSummary) => {
    detailController.current?.abort();
    const controller = new AbortController();
    detailController.current = controller;
    setSelected({ id: run.runId, loading: true, error: "" });
    fetchRun(run.runId, controller.signal)
      .then((data) => !controller.signal.aborted && setSelected({ id: run.runId, dashboard: normalizeDashboard(data), loading: false, error: "" }))
      .catch((error) => {
        const message = errorMessage(error);
        if (message && !controller.signal.aborted) setSelected({ id: run.runId, loading: false, error: message });
      });
  }, []);

  const closeDetail = useCallback(() => {
    detailController.current?.abort();
    detailController.current = null;
    setSelected(null);
  }, []);

  if (selected?.dashboard) return <DashboardDetail dashboard={selected.dashboard} onBack={closeDetail} />;

  if (selected) {
    return (
      <main className="shell state-page">
        <button className="back-button" onClick={closeDetail}>← 返回调查列表</button>
        {selected.loading ? (
          <div className="state-panel"><span className="loader" /><h1>正在整理调查洞察</h1><p>正在读取平台分布、情绪与类别证据…</p></div>
        ) : (
          <div className="state-panel"><div className="empty-glyph error-glyph">!</div><h1>这份调查暂时无法打开</h1><p>{selected.error}</p><button className="button button-primary" onClick={() => loadDetail({ runId: selected.id } as RunSummary)}>重新加载</button></div>
        )}
      </main>
    );
  }

  return <RunList runs={runs} loading={listLoading} error={listError} onRefresh={() => setRefreshKey((key) => key + 1)} onOpen={loadDetail} />;
}
