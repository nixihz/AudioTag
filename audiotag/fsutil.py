"""成品文件的发布方式。

标签写入先落在临时文件上，确认内容无误后再发布到目标路径。
发布要求“目标已存在即失败”，避免并发任务或残留文件被静默覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path


def publish_atomically(temporary: Path, destination: Path) -> None:
    """把临时文件发布为 destination，目标已存在时抛出 FileExistsError。

    优先用硬链接发布：它天然独占，且不会覆盖已存在的同名文件。
    exFAT、FAT 等外置卷不支持硬链接，此时退回重命名，
    这种情况无法保证原子性，因此先确认目标不存在再移动。
    """
    try:
        os.link(temporary, destination)
    except FileExistsError:
        raise
    except OSError:
        if destination.exists():
            raise FileExistsError(f"输出文件已存在：{destination}") from None
        os.replace(temporary, destination)
