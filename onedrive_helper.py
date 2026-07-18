"""
OneDrive sharing link yaratuvchi modul.
Azure app registration siz, faqat bir marta brauzer orqali login kerak.
"""
import os
import json
import subprocess
import requests
import msal

# Microsoft Graph API uchun ochiq client ID (Device Code Flow)
CLIENT_ID  = "d3590ed6-52b3-4102-aeff-aad2292ab01c"  # Microsoft Office — personal + org
AUTHORITY  = "https://login.microsoftonline.com/common"
SCOPES     = ["https://graph.microsoft.com/Files.ReadWrite"]

_SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
_TOKEN_CACHE_FILE = os.path.join(_SCRIPT_DIR, "onedrive_token_cache.bin")


# ─── Token boshqaruvi ────────────────────────────────────────────────────────

def _build_app():
    cache = msal.SerializableTokenCache()
    if os.path.exists(_TOKEN_CACHE_FILE):
        with open(_TOKEN_CACHE_FILE, "r", encoding="utf-8") as f:
            cache.deserialize(f.read())
    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)
    return app, cache


def _save_cache(cache):
    if cache.has_state_changed:
        with open(_TOKEN_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def get_access_token(parent_window=None) -> str:
    """
    Mavjud token qaytaradi; yo'q bo'lsa Device Code Flow orqali yangi token oladi.
    parent_window — tkinter Toplevel yoki None
    """
    app, cache = _build_app()
    accounts = app.get_accounts()
    result = None

    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result or "access_token" not in result:
        # ── Device Code Flow ──────────────────────────────────────────
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow xato: {flow}")

        user_code = flow["user_code"]
        verify_url = flow.get("verification_uri", "https://microsoft.com/devicelogin")

        # Brauzer ochish
        import webbrowser
        webbrowser.open(verify_url)

        # Tkinter dialog — kodni ko'rsatish
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Toplevel(parent_window) if parent_window else tk.Tk()
            if not parent_window:
                root.withdraw()
            messagebox.showinfo(
                "OneDrive — Birinchi ulanish",
                f"Brauzer ochildi: {verify_url}\n\n"
                f"Quyidagi kodni kiriting:\n\n"
                f"          {user_code}\n\n"
                f"Keyin Microsoft akkauntingiz (aizdjlola@gmail.com) bilan kiring.\n\n"
                f"OK bosgach kutiladi...",
                parent=parent_window
            )
            if not parent_window:
                root.destroy()
        except Exception:
            print(f"\n[OneDrive] Saytni oching: {verify_url}")
            print(f"[OneDrive] Kodni kiriting: {user_code}\n")

        result = app.acquire_token_by_device_flow(flow)

    _save_cache(cache)

    if "access_token" in result:
        return result["access_token"]
    raise RuntimeError(f"Token olishda xato: {result.get('error_description', result)}")


# ─── OneDrive root yo'lini aniqlash ─────────────────────────────────────────

def _get_onedrive_root() -> str:
    """Windows registry orqali OneDrive papka yo'lini qaytaradi."""
    # 1. Registry dan
    try:
        ps = (
            "(Get-ItemProperty "
            "'HKCU:\\Software\\Microsoft\\OneDrive' "
            "-Name UserFolder -ErrorAction SilentlyContinue).UserFolder"
        )
        r = subprocess.run(
            ["powershell", "-Command", ps],
            capture_output=True, text=True, timeout=5
        )
        path = r.stdout.strip()
        if path and os.path.isdir(path):
            return path
    except Exception:
        pass

    # 2. Standart yo'llar
    for candidate in [
        os.path.join(os.path.expanduser("~"), "OneDrive"),
        os.path.join(os.environ.get("USERPROFILE", ""), "OneDrive"),
        r"C:\Users\alfatech.uz\OneDrive",
    ]:
        if os.path.isdir(candidate):
            return candidate

    return ""


# ─── Asosiy funksiya ─────────────────────────────────────────────────────────

def create_share_link(local_file_path: str, parent_window=None) -> str:
    """
    OneDrive dagi fayl uchun ommaviy "view" link yaratadi.
    Qaytaradi: URL yoki None (xato bo'lsa)
    """
    if not local_file_path or not os.path.isfile(local_file_path):
        print(f"[OneDrive] Fayl topilmadi: {local_file_path}")
        return None

    od_root = _get_onedrive_root()
    if not od_root:
        print("[OneDrive] OneDrive papkasi aniqlanmadi")
        return None

    # Fayl OneDrive papkasida ekanligini tekshirish
    norm_file = os.path.normcase(os.path.normpath(local_file_path))
    norm_root = os.path.normcase(os.path.normpath(od_root))
    if not norm_file.startswith(norm_root):
        print(f"[OneDrive] Fayl OneDrive da emas: {local_file_path}")
        return None

    rel_path = os.path.relpath(local_file_path, od_root).replace("\\", "/")

    try:
        token = get_access_token(parent_window=parent_window)
    except Exception as e:
        print(f"[OneDrive] Token xato: {e}")
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Graph API: sharing link yaratish
    url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{rel_path}:/createLink"
    body = {"type": "view", "scope": "anonymous"}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=20)
        if resp.status_code in (200, 201):
            share_url = resp.json().get("link", {}).get("webUrl", "")
            if share_url:
                print(f"[OneDrive] ✓ Link: {share_url}")
                return share_url
            print(f"[OneDrive] Javobda link yo'q: {resp.text[:300]}")
        else:
            print(f"[OneDrive] API xato {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"[OneDrive] So'rovda xato: {e}")

    return None


def logout():
    """Saqlangan tokenni o'chiradi (qayta login uchun)."""
    if os.path.exists(_TOKEN_CACHE_FILE):
        os.remove(_TOKEN_CACHE_FILE)
        print("[OneDrive] Token o'chirildi.")


# ─── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("OneDrive ulanishini tekshirish...")
    od = _get_onedrive_root()
    print(f"OneDrive papkasi: {od}")

    # Test: birinchi mavjud faylni topib link olamiz
    if od:
        for root, dirs, files in os.walk(od):
            for f in files:
                if f.endswith((".pdf", ".docx")):
                    test_file = os.path.join(root, f)
                    print(f"Test fayl: {test_file}")
                    link = create_share_link(test_file)
                    print(f"Natija: {link}")
                    break
            else:
                continue
            break
