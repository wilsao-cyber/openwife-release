import logging
import os
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileOpsTool:
    def __init__(self):
        self.allowed_base_paths = [
            Path.home(),
            Path("./mobile_app"),
            Path("./server"),
        ]

    def _is_path_allowed(self, path: str) -> bool:
        target = Path(path).resolve()
        for base in self.allowed_base_paths:
            try:
                target.relative_to(base.resolve())
                return True
            except ValueError:
                continue
        return False

    async def list_directory(self, path: str, recursive: bool = False) -> dict:
        if not self._is_path_allowed(path):
            return {"error": "Path not allowed"}

        try:
            target = Path(path)
            if not target.exists():
                return {"error": f"Path does not exist: {path}"}
            if not target.is_dir():
                return {"error": f"Path is not a directory: {path}"}

            entries = []
            if recursive:
                for item in target.rglob("*"):
                    entries.append(self._format_entry(item, target))
            else:
                for item in target.iterdir():
                    entries.append(self._format_entry(item, target))

            return {"entries": entries, "total": len(entries)}
        except Exception as e:
            logger.error(f"List directory failed: {e}")
            return {"error": str(e)}

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
    VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi", ".mov"}

    async def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        if not self._is_path_allowed(path):
            return {"error": "Path not allowed"}

        try:
            target = Path(path)
            if not target.exists():
                return {"error": f"File does not exist: {path}"}
            if target.is_dir():
                return {"error": f"Path is a directory: {path}"}

            ext = target.suffix.lower()

            # Image files → copy to output and return media
            if ext in self.IMAGE_EXTENSIONS:
                import shutil, uuid, os
                os.makedirs("./output/media", exist_ok=True)
                fname = f"{uuid.uuid4()}{ext}"
                shutil.copy2(str(target), f"./output/media/{fname}")
                return {
                    "path": str(target),
                    "type": "image",
                    "size": target.stat().st_size,
                    "media": [{"type": "image", "url": f"/api/media/{fname}", "alt": target.name}],
                }

            # Video files → copy to output and return media
            if ext in self.VIDEO_EXTENSIONS:
                import shutil, uuid, os
                os.makedirs("./output/media", exist_ok=True)
                fname = f"{uuid.uuid4()}{ext}"
                shutil.copy2(str(target), f"./output/media/{fname}")
                return {
                    "path": str(target),
                    "type": "video",
                    "size": target.stat().st_size,
                    "media": [{"type": "video", "url": f"/api/media/{fname}", "alt": target.name}],
                }

            content = target.read_text(encoding=encoding)
            return {
                "path": str(target),
                "content": content[:50000],
                "size": target.stat().st_size,
            }
        except Exception as e:
            logger.error(f"Read file failed: {e}")
            return {"error": str(e)}

    async def write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> dict:
        if not self._is_path_allowed(path):
            return {"error": "Path not allowed"}

        try:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding=encoding)
            return {"success": True, "path": str(target)}
        except Exception as e:
            logger.error(f"Write file failed: {e}")
            return {"error": str(e)}

    async def delete_file(self, path: str) -> dict:
        if not self._is_path_allowed(path):
            return {"error": "Path not allowed"}

        try:
            target = Path(path)
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return {"success": True, "path": str(path)}
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return {"error": str(e)}

    async def move_file(self, source: str, destination: str) -> dict:
        if not self._is_path_allowed(source) or not self._is_path_allowed(destination):
            return {"error": "Path not allowed"}

        try:
            src = Path(source)
            dst = Path(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {
                "success": True,
                "source": str(source),
                "destination": str(destination),
            }
        except Exception as e:
            logger.error(f"Move failed: {e}")
            return {"error": str(e)}

    async def copy_file(self, source: str, destination: str) -> dict:
        if not self._is_path_allowed(source) or not self._is_path_allowed(destination):
            return {"error": "Path not allowed"}

        try:
            src = Path(source)
            dst = Path(destination)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
            return {
                "success": True,
                "source": str(source),
                "destination": str(destination),
            }
        except Exception as e:
            logger.error(f"Copy failed: {e}")
            return {"error": str(e)}

    async def search_files(self, path: str, pattern: str) -> dict:
        if not self._is_path_allowed(path):
            return {"error": "Path not allowed"}

        try:
            target = Path(path)
            matches = list(target.glob(pattern))
            return {
                "matches": [str(m) for m in matches],
                "total": len(matches),
            }
        except Exception as e:
            logger.error(f"Search files failed: {e}")
            return {"error": str(e)}

    def _format_entry(self, path: Path, base: Path) -> dict:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "relative_path": str(path.relative_to(base)),
            "is_dir": path.is_dir(),
            "size": stat.st_size,
            "modified": stat.st_mtime,
        }
