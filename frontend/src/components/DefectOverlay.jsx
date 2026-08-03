import { useEffect, useRef } from 'react';
import { confidenceColor } from '../utils/colors.js';

/**
 * Canvas overlay. Bounding boxes arrive in source-image pixels; they are scaled
 * to the rendered frame so the drawing stays correct at any display size.
 */
export default function DefectOverlay({ defects = [], sourceWidth, sourceHeight, selectedIndex }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !sourceWidth || !sourceHeight) return undefined;

    const draw = () => {
      const box = canvas.parentElement.getBoundingClientRect();
      if (!box.width) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = box.width * dpr;
      canvas.height = box.height * dpr;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, box.width, box.height);

      const scaleX = box.width / sourceWidth;
      const scaleY = box.height / sourceHeight;
      ctx.font = "600 12px 'Barlow Condensed', sans-serif";

      defects.forEach((d, i) => {
        const b = d.boundingBox || {};
        const x = b.x * scaleX;
        const y = b.y * scaleY;
        const w = b.width * scaleX;
        const h = b.height * scaleY;
        const color = confidenceColor(d.confidence);
        const active = selectedIndex === i;

        ctx.strokeStyle = color;
        ctx.lineWidth = active ? 2.5 : 1.5;
        ctx.strokeRect(x, y, w, h);

        // corner ticks — the system's registration marks, on the detection box
        const t = 9;
        ctx.beginPath();
        [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(
          ([cx, cy, sx, sy]) => {
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx + t * sx, cy);
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx, cy + t * sy);
          },
        );
        ctx.lineWidth = 3;
        ctx.stroke();

        const label = String(i + 1) + '  ' + String(d.type).toUpperCase() + '  ' + Math.round((d.confidence || 0) * 100) + '%';
        const lw = ctx.measureText(label).width + 12;
        const ly = Math.max(0, y - 17);
        ctx.fillStyle = color;
        ctx.fillRect(x, ly, lw, 17);
        ctx.fillStyle = '#f2f2f3';
        ctx.fillText(label, x + 6, ly + 12);
      });
    };

    draw();
    const ro = new ResizeObserver(draw);
    ro.observe(canvas.parentElement);
    return () => ro.disconnect();
  }, [defects, sourceWidth, sourceHeight, selectedIndex]);

  return <canvas ref={canvasRef} className="qc-overlay" aria-hidden="true" />;
}
