/** Nazwy modeli AI dla czytelnika: identyfikator wersji + firma (zamiast skrótów typu „GPT” czy surowych ścieżek dostawcy). */
const COMPANIES: Array<[RegExp, string]> = [
  [/gpt|openai/i, "OpenAI"], [/qwen/i, "Alibaba"], [/nemotron|nvidia/i, "NVIDIA"], [/gemini|gemma/i, "Google"],
  [/mistral/i, "Mistral AI"], [/bielik|speakleash/i, "SpeakLeash / Cyfronet"], [/llama/i, "Meta"],
  [/claude|anthropic/i, "Anthropic"], [/deepseek/i, "DeepSeek"],
];

export function modelCompany(id: string | null | undefined): string | undefined {
  return COMPANIES.find(([pattern]) => pattern.test(id ?? ""))?.[1];
}

/** `speakleash/Bielik-11B-v3.0-Instruct:publicai` → `Bielik-11B-v3.0-Instruct` (bez ścieżki dostawcy i sufiksu hostingu). */
export function modelVersion(id: string | null | undefined): string {
  return (id ?? "").split("/").pop()?.split(":")[0] ?? "";
}

/** „gpt-oss-20b · OpenAI”; zbiorcze „konsylium” opisujemy słowami. */
export function modelFullName(id: string | null | undefined, company?: string | null): string {
  if (!id) return "model nieznany";
  if (id.toLowerCase() === "konsylium") return "Konsylium AI (kilka modeli różnych firm)";
  const firm = company || modelCompany(id);
  return firm ? `${modelVersion(id)} · ${firm}` : modelVersion(id);
}

/** „4/5” → „4 z 5 odpowiadających modeli zgodnych z wynikiem końcowym”; brak liczb → pusty tekst. */
export function agreementWords(agreement: string | null | undefined): string {
  const match = agreement?.match(/^(\d+)\s*\/\s*(\d+)$/);
  return match ? `${match[1]} z ${match[2]} odpowiadających modeli zgodnych z wynikiem końcowym` : "";
}
