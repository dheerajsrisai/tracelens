import { useEffect, useRef, useState } from "react";
import api from "../api";
import { fmtDur } from "../util";

/** Modal that plays a video (jumping to a time) or shows an image, with its detections underneath. */
export default function EvidenceViewer({ item, onClose }) {
  const vid = useRef(null);
  const [tracks, setTracks] = useState([]);
  useEffect(() => { api.get(`/evidence/${item.id}/tracks`).then((r) => setTracks(r.data)).catch(() => {}); }, [item.id]);
  useEffect(() => {
    const key = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  const seek = (s) => { if (vid.current) { vid.current.currentTime = s; vid.current.play().catch(() => {}); } };
  const src = `/api/evidence/${item.id}/file`;

  return (
    <div className="modal" role="dialog" aria-modal="true" aria-label="Evidence viewer" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="row between">
          <strong className="clip">{item.name}</strong>
          <button className="btn ghost small" onClick={onClose}>Close</button>
        </div>
        {item.media_type === "video"
          ? <video ref={vid} src={`${src}#t=${item.offset || 0}`} controls playsInline className="viewer-media" />
          : <img src={src} alt={item.name} className="viewer-media" />}
        {item.media_type === "video" && <p className="muted">If the video does not play, your browser may not support its codec. Download it from the evidence list and open it in a media player.</p>}
        <h3>Detections in this file</h3>
        {tracks.length === 0 ? <p className="muted">No people or vehicles were detected (or analysis is not finished).</p> : (
          <div className="trk-grid">
            {tracks.map((t) => (
              <button key={t.id} className="trk" onClick={() => item.media_type === "video" && seek(t.start_offset)}>
                {t.has_thumb && <img src={`/api/tracks/${t.id}/thumb`} alt="" />}
                <span>{t.cls.toLowerCase()} · {Math.round(t.conf * 100)}%</span>
                {item.media_type === "video" && <span className="mono">{fmtDur(t.start_offset)}</span>}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
