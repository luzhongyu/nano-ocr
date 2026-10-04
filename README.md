# nano-ocr

A minimal OCR tool for Windows. Screenshot → recognize → result is copied to your clipboard automatically.

## Features

- Minimal UI: one screenshot button + one result text box, nothing else
- Global hotkey `Ctrl + Alt + O`: capture any screen region at any time
- Result is automatically copied to the clipboard (right-click in the text box to copy again)
- Optional "hide this window before capture" mode (checkbox)
- Adjustable window width; window size and options are remembered across sessions
- Uses the Windows built-in OCR engine (Windows.Media.Ocr) — **no external programs like Tesseract required**, works offline

## Installation

Requires Python 3.9+ (uses `winsdk` on Python ≤ 3.11, `winrt-*` packages on Python ≥ 3.12):

```powershell
pip install -r requirements.txt
```

## Usage

```powershell
python nano_ocr.py
```

- Click the button or press `Ctrl + Alt + O` to start a capture
- Drag to select a region; release to recognize, `Esc` to cancel, `Enter` to confirm
- The result appears in the window and is copied to the clipboard

## Build a standalone exe

```powershell
pip install pyinstaller
build_exe.bat        # or: python -m PyInstaller --onefile --windowed --name nano-ocr nano_ocr.py
```

The output is `dist\nano-ocr.exe` (~27 MB, single file, portable — copy it to any Windows machine).

## Notes

- The available OCR languages depend on the language packs installed on your system. If no engine is found, add a Chinese or English language pack under
  **Settings → Time & Language → Language & Region**.
- Only for Windows right now.
