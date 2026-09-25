import win32gui

from pywinauto import Desktop


def get_screen_state():
    # Get the handle of the currently active window.
    hwnd = win32gui.GetForegroundWindow()

    # Connect to Windows UI Automation.
    desktop = Desktop(backend="uia")

    # Get the active window.
    window = desktop.window(handle=hwnd)

    state = {
        "window_title": window.window_text(),
        "control_type": window.element_info.control_type,
        "controls": [],
    }

    # Get all controls inside the active window.
    for control in window.descendants():
        try:
            name = control.window_text().strip()
            control_type = control.element_info.control_type
            automation_id = control.element_info.automation_id
            class_name = control.element_info.class_name

            # Ignore completely empty controls.
            if not name and not automation_id and not class_name:
                continue

            state["controls"].append(
                {
                    "name": name,
                    "control_type": control_type,
                    "automation_id": automation_id,
                    "class_name": class_name,
                }
            )

        except Exception:
            # Some Windows controls may disappear while we're reading them.
            continue

    return state


# Get the current screen state.
state = get_screen_state()


# Print it in a readable format.
print("\n=== SCREEN STATE ===")

print("Window:", state["window_title"])
print("Type:", state["control_type"])

print("\nControls:")

for index, control in enumerate(state["controls"][:80]):
    print(
        f"{index:02d}. "
        f"name={control['name']!r} | "
        f"type={control['control_type']!r} | "
        f"id={control['automation_id']!r} | "
        f"class={control['class_name']!r}"
    )