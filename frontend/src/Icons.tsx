/* Inline SVG icon set. Icon-only buttons must carry an aria-label at the call
   site; these are decorative and hidden from assistive technology. */

type Props = { size?: number; className?: string };

function Svg({ size = 16, className, children }: Props & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const IconUpload = (p: Props) => (
  <Svg {...p}><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M4 17v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" /></Svg>
);
export const IconDownload = (p: Props) => (
  <Svg {...p}><path d="M12 4v12" /><path d="m7 11 5 5 5-5" /><path d="M4 19h16" /></Svg>
);
export const IconUp = (p: Props) => (<Svg {...p}><path d="m6 14 6-6 6 6" /></Svg>);
export const IconDown = (p: Props) => (<Svg {...p}><path d="m6 10 6 6 6-6" /></Svg>);
export const IconTrash = (p: Props) => (
  <Svg {...p}><path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /><path d="M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12" /></Svg>
);
export const IconPlus = (p: Props) => (<Svg {...p}><path d="M12 5v14" /><path d="M5 12h14" /></Svg>);
export const IconWarn = (p: Props) => (
  <Svg {...p}><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></Svg>
);
export const IconCheck = (p: Props) => (<Svg {...p}><path d="m4 12 5 5L20 6" /></Svg>);
export const IconImage = (p: Props) => (
  <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="m21 16-5-5L5 20" /></Svg>
);
export const IconUndo = (p: Props) => (
  <Svg {...p}><path d="M3 8h11a5 5 0 0 1 0 10H9" /><path d="m7 4-4 4 4 4" /></Svg>
);
export const IconRedo = (p: Props) => (
  <Svg {...p}><path d="M21 8H10a5 5 0 0 0 0 10h5" /><path d="m17 4 4 4-4 4" /></Svg>
);
export const IconClose = (p: Props) => (<Svg {...p}><path d="M6 6l12 12" /><path d="M18 6 6 18" /></Svg>);
export const IconSparkle = (p: Props) => (
  <Svg {...p}><path d="M12 3v4" /><path d="M12 17v4" /><path d="M3 12h4" /><path d="M17 12h4" /><path d="m5.6 5.6 2.8 2.8" /><path d="m15.6 15.6 2.8 2.8" /><path d="m18.4 5.6-2.8 2.8" /><path d="m8.4 15.6-2.8 2.8" /></Svg>
);
export const IconLayers = (p: Props) => (
  <Svg {...p}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5" /></Svg>
);
export const IconArrowRight = (p: Props) => (<Svg {...p}><path d="M4 12h15" /><path d="m13 6 6 6-6 6" /></Svg>);
