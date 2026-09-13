"use client";
import { useEffect, useRef, type ReactNode } from 'react';
export function Dialog({ open, onClose, title, children, className = '' }: { open: boolean; onClose: () => void; title: string; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    returnFocus.current = document.activeElement as HTMLElement;
    const previous = document.body.style.overflow;
    dialog.showModal();
    dialog.scrollTop = 0;
    document.body.style.overflow = 'hidden';
    return () => {
      dialog.close();
      document.body.style.overflow = previous;
      returnFocus.current?.focus();
    };
  }, [open]);
  return <dialog ref={ref} aria-label={title} onCancel={e => { e.preventDefault(); onClose(); }}
    onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    className={`max-h-[90vh] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto rounded-2xl p-0 shadow-xl backdrop:bg-slate-900/60 backdrop:backdrop-blur-sm ${className}`}>
    <div className="bg-white">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b bg-white p-4">
        <span className="font-semibold">{title}</span><button autoFocus type="button" aria-label="Zamknij okno" className="rounded-lg px-3 py-2 text-primary" onClick={onClose}>Zamknij ×</button>
      </header>{children}
    </div>
  </dialog>;
}
