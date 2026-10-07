const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export type Health = { status: string };

export async function getHealth(): Promise<Health> {
  const response = await fetch(`${apiUrl}/health`);
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<Health>;
}
