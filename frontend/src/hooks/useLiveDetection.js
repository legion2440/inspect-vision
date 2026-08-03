import { useCallback, useEffect, useRef, useState } from 'react';
import { inspectFrame } from '../utils/apiClient.js';

/** Bonus: webcam frames -> POST /api/stream, roughly 2 fps. */
export function useLiveDetection({ fps = 2 } = {}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const controllerRef = useRef(null);
  const activeRef = useRef(false);
  const [running, setRunning] = useState(false);
  const [defects, setDefects] = useState([]);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [error, setError] = useState(null);

  const stop = useCallback(() => {
    activeRef.current = false;
    window.clearTimeout(timerRef.current);
    controllerRef.current?.abort();
    controllerRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setRunning(false);
    setDefects([]);
    setDimensions({ width: 0, height: 0 });
  }, []);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      activeRef.current = true;
      setRunning(true);

      const detectNextFrame = async () => {
        if (!activeRef.current) return;
        const video = videoRef.current;
        try {
          if (video && video.readyState >= 2 && video.videoWidth && video.videoHeight) {
            const width = video.videoWidth;
            const height = video.videoHeight;
            setDimensions({ width, height });

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            canvas.getContext('2d').drawImage(video, 0, 0, width, height);
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.8));
            if (!blob) throw new Error('Could not encode camera frame');

            const controller = new AbortController();
            controllerRef.current = controller;
            const result = await inspectFrame(blob, { signal: controller.signal });
            if (activeRef.current) setDefects(result.defects || []);
          }
        } catch (err) {
          if (err.name !== 'AbortError' && activeRef.current) setError(err.message);
        } finally {
          controllerRef.current = null;
          if (activeRef.current) {
            timerRef.current = window.setTimeout(detectNextFrame, Math.round(1000 / fps));
          }
        }
      };

      detectNextFrame();
    } catch (err) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setError('Camera unavailable: ' + err.message);
    }
  }, [fps]);

  useEffect(() => stop, [stop]);

  return { videoRef, running, defects, dimensions, error, start, stop };
}
