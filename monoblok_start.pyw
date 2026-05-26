import subprocess, os
PYTHON = r"C:\Users\1111111111\AppData\Local\Programs\Python\Python313\python.exe"
SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monoblok_dastur.py")
os.chdir(os.path.dirname(SCRIPT))
subprocess.Popen([PYTHON, SCRIPT], creationflags=subprocess.CREATE_NO_WINDOW)
