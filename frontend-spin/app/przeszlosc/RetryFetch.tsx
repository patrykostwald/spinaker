"use client";
import { installRetryFetch } from './retry-fetch';

// Instalacja przy ładowaniu modułu w przeglądarce, przed efektami komponentów strony (one robią pierwsze zapytania).
if (typeof window !== 'undefined') installRetryFetch(window as unknown as Parameters<typeof installRetryFetch>[0]);

/** Bez widoku: samo załadowanie modułu owija window.fetch (ponawianie odczytów /api/przeszlosc/ po 429 i błędach 502-504). */
export function RetryFetch() { return null; }
