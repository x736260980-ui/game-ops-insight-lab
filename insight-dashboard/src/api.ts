const API_ROOT = "/api/dashboard";

async function fetchJson(path: string, signal?: AbortSignal): Promise<unknown> {
  const response = await fetch(`${API_ROOT}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json() as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {
      // The status code remains useful when the backend did not return JSON.
    }
    throw new Error(detail || `请求失败（HTTP ${response.status}）`);
  }
  return response.json();
}

export async function fetchRuns(signal?: AbortSignal) {
  const data = await fetchJson("/runs", signal);
  if (!data || typeof data !== "object" || !("runs" in data)) return [];
  const runs = (data as { runs?: unknown }).runs;
  return Array.isArray(runs) ? runs : [];
}

export function fetchRun(runId: string, signal?: AbortSignal) {
  return fetchJson(`/runs/${encodeURIComponent(runId)}`, signal);
}

export function fetchCategoryComments(runId: string, categoryId: string, sentiment: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ sentiment });
  return fetchJson(
    `/runs/${encodeURIComponent(runId)}/categories/${encodeURIComponent(categoryId)}/comments?${query}`,
    signal,
  );
}
