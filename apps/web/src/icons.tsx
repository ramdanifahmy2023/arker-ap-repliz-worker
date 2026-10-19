const shapes: Record<string, string> = {
  overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  flow: "M4 3h6v5H4z M14 16h6v5h-6z M4 16h6v5H4z M7 8v4h10v4 M7 12v4",
  worker: "M4 5h16v12H4z M8 21h8 M12 17v4 M8 9l2 2-2 2 M13 13h3",
  alert: "M12 3L2 21h20L12 3z M12 9v5 M12 17v1",
  plus: "M12 5v14 M5 12h14",
  queue: "M8 5h13 M8 12h13 M8 19h13 M3 5h1 M3 12h1 M3 19h1",
  folder: "M3 7V4h6l3 3h9v13H3z",
  play: "M8 5l11 7-11 7z",
  users:
    "M16 21v-3a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v3 M10 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M17 4a4 4 0 0 1 0 7 M18 14a4 4 0 0 1 3 4v3",
  rotate:
    "M20 7a9 9 0 0 0-15-2L2 8 M2 3v5h5 M4 17a9 9 0 0 0 15 2l3-3 M22 21v-5h-5",
  calendar: "M3 5h18v16H3z M7 3v4 M17 3v4 M3 11h18 M7 15h3 M14 15h3",
  send: "M22 2L9 15 M22 2l-7 20-6-7-7-6z",
  film: "M3 3h18v18H3z M7 3v18 M17 3v18 M3 8h4 M3 16h4 M17 8h4 M17 16h4",
  pen: "M4 16l-1 5 5-1L21 7l-5-5z M13 5l5 5",
  message: "M3 3h18v15H8l-5 4z M7 8h10 M7 12h6",
  chart: "M3 3v18h18 M7 16v-5 M12 16V7 M17 16V4",
  link: "M10 13a5 5 0 0 0 7 0l4-4a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7 0l-4 4a5 5 0 0 0 7 7l2-2",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 7-3 10h18c0-3-3-3-3-10 M10 21h4",
  drive: "M5 3h14l3 14H2z M2 17v4h20v-4 M16 18v1 M19 18v1",
  archive: "M3 3h18v5H3z M5 8v13h14V8 M9 12h6",
  history: "M3 11a9 9 0 1 1 2 7 M3 3v8h8 M12 7v5l3 3",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z",
  arrow: "M5 12h14 M14 7l5 5-5 5",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6",
  close: "M5 5l14 14 M19 5L5 19",
  chevron: "M9 5l7 7-7 7",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1 1 M18 18l1 1 M5 19l1-1 M18 6l1-1",
  moon: "M21 13A9 9 0 1 1 11 3a7 7 0 0 0 10 10z",
  menu: "M3 5h18 M3 12h18 M3 19h18",
  logout: "M9 4H3v16h6 M9 12h12 M16 7l5 5-5 5",
  check: "M4 12l5 5L20 6",
  pause: "M8 4v16 M16 4v16",
  shield: "M12 2l9 4v6c0 6-9 10-9 10S3 18 3 12V6z",
  external: "M14 3h7v7 M10 14L21 3 M10 3H3v18h18v-7",
  download: "M12 3v12 M7 10l5 5 5-5 M3 15v6h18v-6",
};
export function Icon({ name, size = 20 }: { name: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={shapes[name] || shapes.overview} />
    </svg>
  );
}
