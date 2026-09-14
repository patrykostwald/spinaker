"use client";

type ShareOnXProps = {
  title: string;
  path: string;
  label?: string;
};

export function ShareOnX({ title, path, label = "Udostępnij na X" }: ShareOnXProps) {
  const share = () => {
    const url = new URL(path, window.location.origin).toString();
    const params = new URLSearchParams({ text: title, url });
    window.open(
      `https://x.com/intent/tweet?${params.toString()}`,
      "spin-clinic-x-share",
      "popup=yes,width=620,height=640,scrollbars=yes,resizable=yes",
    );
  };

  return <button type="button" className="quiet-button share-x-button" onClick={share}>
    {label} ↗
  </button>;
}
