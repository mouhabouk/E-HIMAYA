import { useId, useState, type DragEvent } from "react";

/** File input that also accepts drag-and-drop (the input stays the keyboard and screen-reader path). */
export function FileDrop({
  label,
  hint,
  accept,
  onFile,
  disabled = false,
}: {
  label: string;
  hint?: string;
  accept: string;
  onFile: (file: File) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [over, setOver] = useState(false);
  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files[0];
    if (file && !disabled) onFile(file);
  }
  return (
    <div
      className={`drop${over ? " drop--over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      data-testid="file-drop"
    >
      <label htmlFor={id}>{label}</label>
      {hint && <p className="muted drop__hint">{hint}</p>}
      <input
        id={id}
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
          e.target.value = "";
        }}
      />
    </div>
  );
}
