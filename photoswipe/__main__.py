from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="photoswipe",
        description="PhotoSwipe — a fast desktop photo culling app",
    )
    parser.add_argument(
        "--data-dir",
        help="Folder for settings, sessions and cache (system location by default)",
    )
    parser.add_argument(
        "folder",
        nargs="?",
        help="Folder to add and open on startup",
    )
    parser.add_argument(
        "--portable",
        action="store_true",
        help="Keep settings and cache next to the executable in PhotoSwipeData",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    return parser.parse_args(argv)


def portable_root() -> Path:
    """Folder that contains the executable, or the source checkout in dev mode."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def portable_data_dir() -> Path:
    return portable_root() / "PhotoSwipeData"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(sys.argv[1:] if argv is None else argv))
    if args.version:
        from . import __version__

        print(f"PhotoSwipe {__version__}")
        return 0
    if args.data_dir:
        os.environ["PHOTOSWIPE_DATA_DIR"] = str(
            Path(args.data_dir).expanduser().resolve()
        )
    elif args.portable or (portable_root() / "portable.flag").is_file():
        os.environ.setdefault("PHOTOSWIPE_DATA_DIR", str(portable_data_dir()))

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from . import __version__
    from .paths import data_dir, ensure_dirs
    from .ui.icons import brand_pixmap
    from .ui.main_window import MainWindow
    from .ui.theme import apply_theme

    ensure_dirs()
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PhotoSwipe.Desktop"
            )
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv[:1])
    app.setApplicationName("PhotoSwipe")
    app.setApplicationDisplayName("PhotoSwipe")
    app.setOrganizationName("PhotoSwipe")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(brand_pixmap(64)))
    if sys.platform.startswith("linux"):
        app.setDesktopFileName("photoswipe")
    apply_theme(app)

    def exception_hook(exc_type, exc_value, exc_tb) -> None:
        detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log = data_dir() / "error.log"
            with log.open("a", encoding="utf-8") as handle:
                handle.write(detail + "\n")
        except OSError:
            pass
        try:
            QMessageBox.critical(
                None,
                "PhotoSwipe — error",
                f"Something went wrong.\n\n{exc_value}\n\nDetails were written to error.log.",
            )
        except Exception:
            print(detail, file=sys.stderr)

    sys.excepthook = exception_hook
    window = MainWindow()
    window.show()
    if args.folder:
        QTimer.singleShot(0, lambda: window.open_folder(args.folder))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
