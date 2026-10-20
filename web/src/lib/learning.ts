export async function learningFetch<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, body === undefined ? {cache:"no-store"} :
    {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail || `The workbench returned HTTP ${response.status}.`);
  return data;
}
