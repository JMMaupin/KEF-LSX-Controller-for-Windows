"""The small windows of installation and removal.

Shown before the application exists -- no tray icon, no main window yet --,
each runs its own short Tk loop and returns the choice made.
"""

import customtkinter as ctk

from . import __version__, paths, product, version_tuple
from .paths import is_frozen


def _icon_path():
    import sys
    from pathlib import Path
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "Kef-LSX-HP.ico"


def _window():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title(product.APP_NAME)
    root.resizable(False, False)
    try:
        root.iconbitmap(str(_icon_path()))
    except Exception:
        pass
    body = ctk.CTkFrame(root, fg_color="transparent")
    body.pack(fill="both", expand=True, padx=24, pady=20)
    return root, body


def _center(root):
    root.update_idletasks()
    width, height = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 3
    root.geometry(f"+{x}+{y}")
    root.lift()
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))


def _heading(body, text):
    ctk.CTkLabel(body, text=text, font=ctk.CTkFont(size=15, weight="bold"),
                 anchor="w", justify="left").pack(anchor="w")


def _text(body, text):
    ctk.CTkLabel(body, text=text, wraplength=420, justify="left",
                 anchor="w").pack(anchor="w", pady=(8, 16))


def ask_setup(installed):
    """What to do with this executable: "install", "run", "open" or "cancel".

    - nothing installed: install, or run it as it is;
    - an older version installed: update it;
    - the same one: open it, or reinstall it;
    - a newer one: open the installed copy.
    """
    app = product.APP_NAME
    if installed is None:
        heading = f"Install {app} {__version__}"
        text = (f"It goes to {paths.install_dir()}, with a Start menu shortcut, "
                "and starts with Windows. Windows will ask for an administrator.")
        buttons = [("install", "Install"), ("run", "Run without installing")]
    elif version_tuple(installed) < version_tuple(__version__):
        heading = f"Update {app} {installed} to {__version__}"
        text = ("The running application closes during the update and starts "
                "again afterwards. Your settings are kept. Windows will ask for "
                "an administrator.")
        buttons = [("install", "Update"), ("run", "Run without installing")]
    elif version_tuple(installed) == version_tuple(__version__):
        heading = f"{app} {installed} is already installed"
        # Reinstalling the same version repairs a damaged installation.
        text = "Open the installed copy, or reinstall it to repair it."
        buttons = [("open", "Open"), ("install", "Reinstall")]
    else:
        heading = f"{app} {installed} is already installed"
        text = f"This file is version {__version__}. Open the installed copy instead?"
        buttons = [("open", "Open"), ("run", "Run this file anyway")]
    buttons.append(("cancel", "Cancel"))

    root, body = _window()
    choice = {"value": "cancel"}
    _heading(body, heading)
    _text(body, text)
    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(anchor="e")

    def pick(value):
        choice["value"] = value
        root.destroy()

    for index, (value, label) in enumerate(buttons):
        button = ctk.CTkButton(
            row, text=label, width=90, command=lambda v=value: pick(v),
            fg_color=None if index == 0 else "gray30",
            hover_color=None if index == 0 else "gray40")
        button.pack(side="left", padx=(0 if index == 0 else 8, 0))
    root.bind("<Return>", lambda _e: pick(buttons[0][0]))
    root.bind("<Escape>", lambda _e: pick("cancel"))
    root.protocol("WM_DELETE_WINDOW", lambda: pick("cancel"))
    _center(root)
    root.mainloop()
    return choice["value"]


def confirm_uninstall():
    """Ask before removing: (go ahead, also delete the settings)."""
    root, body = _window()
    result = {"go": False}
    _heading(body, f"Uninstall {product.APP_NAME}?")
    _text(body, "The application closes and is removed from this PC.")
    keep = ctk.BooleanVar(root, value=True)
    ctk.CTkCheckBox(body, text="Keep the settings (speaker IP address)",
                    variable=keep).pack(anchor="w", pady=(0, 16))
    row = ctk.CTkFrame(body, fg_color="transparent")
    row.pack(anchor="e")

    def go():
        result["go"] = True
        root.destroy()

    ctk.CTkButton(row, text="Uninstall", width=90, command=go).pack(side="left")
    ctk.CTkButton(row, text="Cancel", width=90, fg_color="gray30",
                  hover_color="gray40", command=root.destroy).pack(
        side="left", padx=(8, 0))
    root.bind("<Escape>", lambda _e: root.destroy())
    _center(root)
    root.mainloop()
    return result["go"], not keep.get()


def show_message(text, error=False):
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    try:
        root.iconbitmap(str(_icon_path()))
    except Exception:
        pass
    (messagebox.showerror if error else messagebox.showinfo)(
        product.APP_NAME, text, parent=root)
    root.destroy()
