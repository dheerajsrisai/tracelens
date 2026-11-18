import mimetypes
import re
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse


def ranged_file(path: Path, request: Request, media_type: str = None):
    """Serve a file with HTTP Range support so the browser can seek inside videos."""
    if not path.exists():
        raise HTTPException(404, "File not found")
    media_type = media_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    size = path.stat().st_size
    header = request.headers.get("range")
    base = {"Accept-Ranges": "bytes", "X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"}
    if not header:
        return FileResponse(path, media_type=media_type, headers=base)
    m = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        raise HTTPException(416, "Bad range")
    if m.group(1) == "":                                  # suffix range: last N bytes
        start, end = max(0, size - int(m.group(2))), size - 1
    else:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
    if start > end or start >= size:
        raise HTTPException(416, "Range not satisfiable", headers={"Content-Range": f"bytes */{size}"})

    def stream():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    headers = {**base, "Content-Range": f"bytes {start}-{end}/{size}", "Content-Length": str(end - start + 1)}
    return StreamingResponse(stream(), status_code=206, media_type=media_type, headers=headers)
