import { FAMILY_OF, TECHNIQUE_FAMILIES } from "./techniqueFamilies";

type Technique = { name: string; category?: string; family?: string; quote?: string; explanation?: string };
type Vote = { model: string; verdict: string | null; intensity: number | null; status?: string };
type DiagnosisInput<T extends Technique> = {
  verdict?: string;
  techniques?: T[];
  claims?: Array<{ assessment: string }>;
  council?: { members?: Vote[] } | null;
  scan?: { techniques?: Technique[]; council?: { votes?: Vote[] } };
};

export const CLAIM_ASSESSMENTS = [
  ["supported", "ok", "potwierdzone"],
  ["misleading", "mid", "mylące"],
  ["contradicted", "bad", "sprzeczne"],
  ["unverified", "unverified", "niesprawdzone"],
  ["opinion", "op", "opinia"],
] as const;

/** Jedna lista dla licznika, pasków, tabeli i uzasadnienia. Nie klasyfikujemy nazw historycznych. */
export function diagnosisPresentation<T extends Technique>(input: DiagnosisInput<T>) {
  // Pełna diagnoza ma pierwszeństwo: stare scan.techniques jest ucięte do sześciu pozycji.
  const source: Technique[] = input.techniques ?? input.scan?.techniques ?? [];
  const techniques = source.map(item => {
    const category = item.category?.trim();
    const scanned = input.scan?.techniques?.find(other =>
      category ? other.category === category : other.name === item.name);
    const key = category || item.name;
    const family = FAMILY_OF[key] ?? Object.entries(FAMILY_OF).find(([name]) => name.toLocaleLowerCase("pl-PL") === key.toLocaleLowerCase("pl-PL"))?.[1]
      ?? scanned?.family ?? item.family;
    return {
      ...item,
      type: category || item.name,
      label: scanned?.name || category || item.name,
      family: TECHNIQUE_FAMILIES.some(([key]) => key === family) ? family! : "inne",
    };
  });
  const types = techniques.filter((item, index, all) => all.findIndex(other => other.type === item.type) === index);
  const families = TECHNIQUE_FAMILIES.map(([key, label]) => ({
    key, label, types: types.filter(item => item.family === key),
    count: types.filter(item => item.family === key).length,
  })).filter(family => family.key !== "inne" || family.count > 0);

  // Liczymy zapisane pozycje analizy, bez scalania podobnych zdań i bez wnioskowania ze źródeł.
  const claims = CLAIM_ASSESSMENTS.map(([key, kind, label]) => ({
    key, kind, label, count: (input.claims ?? []).filter(claim => claim.assessment === key).length,
  }));
  const checked = claims.filter(item => ["supported", "misleading", "contradicted"].includes(item.key))
    .reduce((sum, item) => sum + item.count, 0);

  // Pełny skład zawiera również modele pominięte przez stare scan.council.votes.
  const votes = (input.council?.members ?? input.scan?.council?.votes ?? []).map(vote => ({
    ...vote,
    missing: vote.status === "brak odpowiedzi" || !["spin", "partial", "no_spin", "unclear"].includes(vote.verdict ?? ""),
  }));
  const responses = votes.filter(vote => !vote.missing);
  const missing = votes.filter(vote => vote.missing);
  // Zgodność liczymy względem końcowego werdyktu diagnozy (np. 2× „nie da się ocenić” + 1× „spin” przy wyniku „spin” = 1/3).
  const sameVerdict = input.verdict
    ? responses.filter(vote => vote.verdict === input.verdict).length
    : Math.max(0, ...responses.map(vote => responses.filter(other => other.verdict === vote.verdict).length));
  return {
    techniques, types, families, typeCount: types.length,
    familyMax: Math.max(1, ...families.map(family => family.count)),
    claims, checked,
    claimSquares: claims.flatMap(claim => Array<string>(claim.count).fill(claim.kind)),
    council: {
      votes, responses, missing, sameVerdict,
      disagreementCount: responses.length - sameVerdict,
      agreement: responses.length ? `${sameVerdict}/${responses.length}` : null,
    },
  };
}
