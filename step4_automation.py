from pywinauto import Desktop


desktop = Desktop(backend="uia")

windows = desktop.windows(visible_only=True)

print("\n=== VISIBLE WINDOWS ===")

for window in windows:
    try:
        title = window.window_text()

        if title.strip():
            print(
                f"Title: {title!r} | "
                f"Control type: {window.element_info.control_type}"
            )

    except Exception:
        pass