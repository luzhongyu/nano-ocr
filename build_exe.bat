@echo off
rem One-file, no-console build. Output: dist\nano-ocr.exe
python -m PyInstaller --onefile --windowed --name nano-ocr --clean -y nano_ocr.py
