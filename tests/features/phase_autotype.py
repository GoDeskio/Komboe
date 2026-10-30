# Desktop auto-type.
import time
from komboe.platform.autotype import sequence_for, type_into
@t(90)
def _():
    import tkinter as tk
    os.environ.setdefault("DISPLAY", ":1")
    username, password = "ada-type", "autotype-secret-90"
    steps = sequence_for([{"name": "Northern Bank", "username": username, "password": password, "uri": "https://north.example"}], "Northern Bank Login")
    assert steps == [username, "tab", password, "enter"]
    assert sequence_for([{"name": "Other", "username": "x", "password": "y", "uri": ""}], "Northern Bank Login") is None
    root = tk.Tk()
    root.title("Northern Bank Login")
    user_var, pass_var, done = tk.StringVar(), tk.StringVar(), tk.StringVar()
    first = tk.Entry(root, textvariable=user_var, width=80)
    second = tk.Entry(root, textvariable=pass_var, width=80)
    first.pack(); second.pack()
    def finish(_event=None):
        done.set(user_var.get() + "|" + pass_var.get())
    second.bind("<Return>", finish)
    first.focus_force()
    root.geometry("640x120+40+40")
    root.update_idletasks(); root.update()
    type_into(str(root.winfo_id()), steps)
    for _ in range(50):
        root.update()
        if done.get():
            break
        time.sleep(0.05)
    root.destroy()
    assert done.get() == f"{username}|{password}", done.get()
    return DONE("auto-type matches the window title and types the username and password into that window")
