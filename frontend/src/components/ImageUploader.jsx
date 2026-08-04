import { useRef, useState } from 'react';
import { Upload } from 'lucide-react';
import Blueprint from './Blueprint.jsx';
import { acceptAttr, validateImage } from '../utils/validateImage.js';

/** Drag-and-drop + explicit file-picker button with client-side validation. */
export default function ImageUploader({ onFile, compact = false, error }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState(null);

  const accept = (file) => {
    const invalid = validateImage(file);
    setLocalError(invalid);
    if (!invalid) onFile(file);
  };

  return (
    <div>
      <Blueprint
        className={'qc-drop' + (dragging ? ' is-dragging' : '') + (compact ? ' is-compact' : '')}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer.files?.[0];
          if (file) accept(file);
        }}
      >
        <Upload size={compact ? 26 : 34} strokeWidth={1.5} color="var(--color-accent)" />
        <div>
          <h4>Drop a part image here</h4>
          <p className="text-muted qc-drop-hint">
            JPG / PNG, up to 10 MB, 640×640 to 1920×1080
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary qc-choose-image"
          onClick={() => inputRef.current?.click()}
        >
          <Upload size={16} strokeWidth={1.5} /> Choose image
        </button>
        <span className="qc-mono qc-drop-endpoint">POST /api/inspect</span>
        <input
          ref={inputRef}
          type="file"
          accept={acceptAttr}
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) accept(file);
            e.target.value = '';
          }}
        />
      </Blueprint>
      {(localError || error) && <p className="qc-error">{localError || error}</p>}
    </div>
  );
}
