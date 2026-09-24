"use client";

import type { Article } from '@spin-clinic/ui';
import { MaterialSurface } from '@spin-clinic/ui/kit';

export default function MaterialView({ article }: { article: Article }) {
  return <MaterialSurface mode="page" article={article} />;
}
