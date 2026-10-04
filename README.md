# nano-ocr

Windows 极简 OCR 工具。截图 → 识别 → 结果自动进剪贴板。

## 功能

- 一个截图按钮 + 一个结果文本框，没有多余的界面
- 全局快捷键 `Ctrl + Alt + O`：随时框选屏幕任意区域进行识别
- 结果自动复制到剪贴板（也可在文本框中右键复制）
- 使用 Windows 系统自带 OCR 引擎（Windows.Media.Ocr），**无需安装 Tesseract 等外部程序**，离线可用

## 安装

需要 Python 3.9+（3.11 及以下自动使用 winsdk，3.12+ 自动使用 winrt 包）：

```powershell
pip install -r requirements.txt
```

## 运行

```powershell
python nano_ocr.py
```

- 点击按钮或按 `Ctrl + Alt + O` 开始截图
- 拖拽框选要识别的区域，松开鼠标即开始识别；`Esc` 取消，`Enter` 确认
- 识别结果显示在窗口中，并自动复制到剪贴板

## 注意

- OCR 语言取决于系统已安装的语言包。若提示无可用引擎，请在
  **设置 → 时间和语言 → 语言和区域** 中添加中文或英文语言包。

## 打包成 exe

```powershell
pip install pyinstaller
build_exe.bat        # 或: python -m PyInstaller --onefile --windowed --name nano-ocr nano_ocr.py
```

产物在 `dist\nano-ocr.exe`（约 27 MB，单文件、绿色免安装，可拷贝到任意 Windows 机器运行）。

