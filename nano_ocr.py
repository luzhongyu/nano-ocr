"""nano-ocr: 极简 Windows OCR 工具

- 全局快捷键 Ctrl+Alt+O：截取屏幕选区并识别
- 主窗口：一个截图按钮 + 一个结果文本框（结果自动复制到剪贴板）
- OCR 使用 Windows 系统自带引擎（Windows.Media.Ocr），无需外部程序
"""

import asyncio
import ctypes
import io
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter.scrolledtext import ScrolledText

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 高分屏下坐标与像素一致
except Exception:
    pass

import keyboard
import mss
from PIL import Image, ImageTk

# Windows 运行时 OCR：winsdk (Python<=3.11) 或 winrt-* (Python>=3.12)
try:
    from winsdk.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
except ImportError:
    from winrt.windows.graphics.imaging import BitmapDecoder, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

HOTKEY = "ctrl+alt+o"
CONFIG_FILE = Path.home() / ".nano_ocr.json"
BTN_BG, BTN_HOVER, BTN_DISABLED = "#2563eb", "#3b82f6", "#93a3d8"


# ---------- OCR ----------

def _get_engine():
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine:
        return engine
    for lang in OcrEngine.available_recognizer_languages:
        engine = OcrEngine.try_create_from_language(lang)
        if engine:
            return engine
    return None


async def _ocr_image(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    writer.write_bytes(buf.getvalue())
    await writer.store_async()
    await writer.flush_async()

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    if bitmap.bitmap_pixel_format != BitmapPixelFormat.BGRA8:
        bitmap = SoftwareBitmap.convert(bitmap, BitmapPixelFormat.BGRA8)

    engine = _get_engine()
    if engine is None:
        raise RuntimeError("未找到可用的 OCR 语言包，请在系统设置中添加语言（如中文/英文）")
    result = await engine.recognize_async(bitmap)
    return result.text


def ocr_image(img: Image.Image) -> str:
    return asyncio.run(_ocr_image(img))


# ---------- 界面 ----------

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.tasks = queue.Queue()
        self._overlay = None

        root.title("nano-ocr")
        root.minsize(360, 240)
        config = self._load_config()
        root.geometry(config.get("geometry", "460x330"))
        root.configure(bg="#f5f6f8")
        self.hide_var = tk.BooleanVar(value=config.get("hide", True))

        self.btn = tk.Button(
            root, text=f"截图识别  ({HOTKEY.upper().replace('+', ' + ')})",
            font=("Microsoft YaHei UI", 11, "bold"), pady=8,
            bg=BTN_BG, fg="white",
            activebackground=BTN_HOVER, activeforeground="white",
            disabledforeground="white",
            relief="flat", bd=0, cursor="hand2",
            command=self.start_capture,
        )
        self.btn.pack(fill="x", padx=12, pady=(12, 6))
        self.btn.bind("<Enter>", lambda e: self._style_btn(hover=True))
        self.btn.bind("<Leave>", lambda e: self._style_btn())

        self.hide_chk = tk.Checkbutton(
            root, text="截图时隐藏本窗口", variable=self.hide_var,
            font=("Microsoft YaHei UI", 9), bg="#f5f6f8",
            fg="#555b66", activebackground="#f5f6f8",
            cursor="hand2",
        )
        self.hide_chk.pack(anchor="w", padx=12)

        self.text = ScrolledText(
            root, font=("Microsoft YaHei UI", 11), height=8, wrap="word",
            relief="flat", bd=0, padx=10, pady=8,
            background="white", highlightthickness=1,
            highlightbackground="#e2e5ea", highlightcolor="#93a3d8",
        )
        self.text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.text.configure(state="disabled")
        self.text.bind("<Button-3>", lambda e: self.copy_result())

        keyboard.add_hotkey(HOTKEY, lambda: self.tasks.put("capture"))
        root.after(50, self._poll_tasks)
        root.protocol("WM_DELETE_WINDOW", self.quit)

    def quit(self):
        try:
            CONFIG_FILE.write_text(json.dumps({
                "geometry": self.root.geometry(),
                "hide": bool(self.hide_var.get()),
            }))
        except Exception:
            pass
        keyboard.unhook_all()
        self.root.destroy()

    @staticmethod
    def _load_config():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            return {}

    def _style_btn(self, hover=False):
        state = str(self.btn["state"])
        self.btn.configure(bg=BTN_DISABLED if state == "disabled"
                           else (BTN_HOVER if hover else BTN_BG))

    # -- 任务轮询（保证所有 UI 操作都在主线程执行） --
    def _poll_tasks(self):
        try:
            while True:
                task = self.tasks.get_nowait()
                if task == "capture":
                    self.start_capture()
                elif isinstance(task, tuple) and task[0] == "result":
                    self._set_result(task[1])
        except queue.Empty:
            pass
        self.root.after(50, self._poll_tasks)

    # -- 截图选区 --
    def start_capture(self):
        self.btn.configure(text="识别中...", state="disabled")
        self._style_btn()
        if self.hide_var.get():
            self.root.withdraw()
            self.root.after(200, self._show_overlay)  # 等窗口真正从屏幕上消失
        else:
            self._show_overlay()  # 直接截图：主窗口保留在屏幕上

    def _show_overlay(self):
        with mss.MSS() as sct:
            monitor = sct.monitors[0]  # 虚拟桌面（覆盖所有显示器）
            shot = sct.grab(monitor)
        self._img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.geometry(f"{shot.width}x{shot.height}+{monitor['left']}+{monitor['top']}")
        top.attributes("-topmost", True)

        canvas = tk.Canvas(top, cursor="cross", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        self._photo = ImageTk.PhotoImage(self._img)
        canvas.create_image(0, 0, image=self._photo, anchor="nw")

        self._canvas = canvas
        self._sel = None
        self._rect = None
        self._cur = None
        canvas.bind("<ButtonPress-1>", self._on_press)
        canvas.bind("<B1-Motion>", self._on_drag)
        canvas.bind("<ButtonRelease-1>", self._on_release)
        canvas.bind("<Escape>", lambda e: self._cancel(top))
        canvas.bind("<Return>", lambda e: self._confirm())
        canvas.focus_set()
        self._overlay = top

    def _on_press(self, event):
        self._sel = (event.x, event.y)
        self._cur = (event.x, event.y)

    def _on_drag(self, event):
        if self._sel:
            self._cur = (event.x, event.y)
            x0, y0 = self._sel
            if self._rect:
                self._canvas.delete(self._rect)
            self._rect = self._canvas.create_rectangle(
                x0, y0, event.x, event.y, outline="#ff3b30", width=2
            )

    def _on_release(self, event):
        if self._sel:
            self._cur = (event.x, event.y)
            self._confirm()

    def _confirm(self):
        if not self._sel:
            self._cancel()
            return
        x1, y1 = self._sel
        x2, y2 = self._cur
        box = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        if box[2] - box[0] < 3 or box[3] - box[1] < 3:  # 误触（几乎没有选区）
            self._cancel()
            return
        img = self._img.crop(box)
        self._cleanup_overlay()
        self.root.deiconify()
        threading.Thread(target=self._do_ocr, args=(img,), daemon=True).start()

    def _cleanup_overlay(self):
        self._sel = None
        self._rect = None
        self._canvas = None
        if self._overlay:
            self._overlay.destroy()
            self._overlay = None

    def _cancel(self, event=None):
        self._cleanup_overlay()
        self.btn.configure(text=f"截图识别  ({HOTKEY.upper().replace('+', ' + ')})", state="normal")
        self._style_btn()
        self.root.deiconify()

    # -- OCR 与结果 --
    def _do_ocr(self, img: Image.Image):
        try:
            text = ocr_image(img).strip()
        except Exception as e:
            text = f"识别失败: {e}"
        self.tasks.put(("result", text))

    def _set_result(self, text: str):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")
        self.btn.configure(text=f"截图识别  ({HOTKEY.upper().replace('+', ' + ')})", state="normal")
        self._style_btn()
        if text and not text.startswith("识别失败"):
            self.copy_result()

    def copy_result(self):
        text = self.text.get("1.0", "end-1c")
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
