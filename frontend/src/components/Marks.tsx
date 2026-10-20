import { useId } from "react";

const KINDS: [RegExp, string, string][] = [
  [/\.pdf$/i, "PDF", "pdf"],
  [/\.(png|jpe?g|tiff?|bmp|webp)$/i, "ẢNH", "img"],
  [/\.docx?$/i, "DOC", "doc"],
  [/\.xlsx?$/i, "XLS", "xls"],
  [/\.pptx?$/i, "PPT", "ppt"],
  [/\.html?$/i, "HTML", "html"],
];

/** Small dog-eared sheet labelled with the file type. */
export function FileBadge({ filename }: { filename: string }) {
  const [, label, kind] = KINDS.find(([re]) => re.test(filename)) ?? [null, "TỆP", "other"];
  return (
    <span className={`file-badge fb-${kind}`} aria-hidden>
      {label}
    </span>
  );
}

/** Red round seal stamped on a dossier once it has been fully read. */
export function Seal() {
  const id = useId().replace(/:/g, "");
  return (
    <span className="seal" role="img" aria-label="Đã số hoá">
      <svg viewBox="0 0 100 100" aria-hidden>
        <defs>
          <path id={`arc-${id}`} d="M 50 50 m -33 0 a 33 33 0 1 1 66 0 a 33 33 0 1 1 -66 0" />
        </defs>
        <circle cx="50" cy="50" r="46" className="ring" />
        <circle cx="50" cy="50" r="24" className="ring thin" />
        <text className="arc">
          {/* stretched over the whole ring (2π·33 ≈ 207) so the legend closes on itself */}
          <textPath href={`#arc-${id}`} startOffset="0" textLength="203" lengthAdjust="spacing">
            ĐÃ SỐ HOÁ · HỒ SƠ TÍN DỤNG ·
          </textPath>
        </text>
        <path className="star" d="M50 36 l4.1 8.4 9.3 1.3 -6.7 6.5 1.6 9.2 -8.3 -4.4 -8.3 4.4 1.6 -9.2 -6.7 -6.5 9.3 -1.3z" />
      </svg>
    </span>
  );
}
