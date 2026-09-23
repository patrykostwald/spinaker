"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionRoot } from "@spin-clinic/ui/kit";
import { useState, type ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 60_000, refetchOnWindowFocus: false },
        },
      }),
  );
  return (
    <MotionRoot>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </MotionRoot>
  );
}
