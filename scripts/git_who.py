import os
import subprocess

GIT = os.path.join(os.environ["LOCALAPPDATA"], r"GitHubDesktop\app-3.5.8\resources\app\git\cmd\git.exe")

def run(*args):
    out = subprocess.run([GIT, *args], capture_output=True, text=True, encoding="utf-8", cwd=".")
    return (out.stdout + out.stderr).strip()

print("user.name:", run("config", "user.name") or "(unset)")
print("user.email:", run("config", "user.email") or "(unset)")
print("last:", run("log", "-1", "--format=%an <%ae>"))
