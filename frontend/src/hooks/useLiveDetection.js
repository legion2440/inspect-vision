import { useCallback, useEffect, useRef, useState } from 'react';
import { inspectFrame } from '../utils/apiClient.js';

/** Bonus: webcam frames -> POST /api/stream, roughly 2 fps. */
export function useLiveDetection({ fps = 2 } = {}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timer = useRef(null);
  const [running, setRunning] = useState(false);
  const [defects, setDefects] = useState([]);
  const [error, setError] = useState(null);

  const stop = useCallback(() => {
    clearInterval(timer.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setRunning(false);
    setDefects([]);
  }, []);

  const start = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setRunning(true);
      timer.current = setInterval(async () => {
        const video = videoRef.current;
        if (!video || video.readyState < 2) return;
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', 0.8));
        try {
          const result = await inspectFrame(blob);
          setDefects(result.defects || []);
        } catch (err) {
          setError(err.message);
        }
      }, Math.round(1000 / fps));
    } catch (err) {
      setError('Camera unavailable: ' + err.message);
    }
  }, [fps]);

  useEffect(() => stop, [stop]);

  return { videoRef, running, defects, error, start, stop };
}
