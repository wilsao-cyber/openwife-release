import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_VRM_SIZE = 500 * 1024 * 1024
GLTF_MAGIC = b'glTF'


class VrmManager:
    def __init__(self, vrm_dir: str = "./output/vrm"):
        self.vrm_dir = Path(vrm_dir)
        self.vrm_dir.mkdir(parents=True, exist_ok=True)

    def _validate(self, data: bytes, filename: str) -> None:
        if len(data) > MAX_VRM_SIZE:
            raise ValueError(f"File exceeds {MAX_VRM_SIZE // (1024*1024)}MB limit")
        if data[:4] != GLTF_MAGIC:
            raise ValueError("Invalid VRM file: missing glTF magic bytes")
        if not filename.endswith('.vrm'):
            raise ValueError("Filename must end with .vrm")

    def save(self, data: bytes, filename: str) -> str:
        self._validate(data, filename)
        path = self.vrm_dir / filename
        path.write_bytes(data)
        logger.info(f"VRM saved: {filename} ({len(data)} bytes)")
        return filename

    def list_models(self) -> list[dict]:
        result = []
        for f in sorted(self.vrm_dir.glob("*.vrm")):
            stat = f.stat()
            result.append({
                "filename": f.name,
                "size": stat.st_size,
                "uploaded_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        return result

    def delete(self, filename: str) -> None:
        path = self.vrm_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"VRM file not found: {filename}")
        path.unlink()
        logger.info(f"VRM deleted: {filename}")

    def get_path(self, filename: str) -> str:
        path = self.vrm_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"VRM file not found: {filename}")
        return str(path)
