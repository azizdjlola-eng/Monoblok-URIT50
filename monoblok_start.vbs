' ─────────────────────────────────────────────────────────────────────────
'  Natija (Monoblok) dasturini yashirin (konsolsiz) ishga tushiradi.
'
'  QOIDA (2026-08-15): Python yo'li QATTIQ YOZILMAYDI. Ilgari bu yerda
'  "C:\Users\1111111111\...\python.exe" turardi — o'sha nomdagi foydalanuvchi
'  yo'q kompyuterda bu fayl JIMGINA hech narsa qilmasdi. Endi Python shu
'  kompyuterda qidiriladi, topilmasa PATH dagi "py" ishlatiladi.
'
'  DIQQAT: oyna rejimi 0 (yashirin) — konsol yaratiladi, lekin ko'rinmaydi.
'  Bu MUHIM: konsol umuman bo'lmasa monoblokning print() lari xato beradi.
' ─────────────────────────────────────────────────────────────────────────
Set WShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

papka  = fso.GetParentFolderName(WScript.ScriptFullName)
skript = fso.BuildPath(papka, "monoblok_dastur.py")

lokal = WShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
nomzodlar = Array( _
    lokal & "\Programs\Python\Python313\python.exe", _
    lokal & "\Programs\Python\Python312\python.exe", _
    lokal & "\Programs\Python\Python311\python.exe", _
    lokal & "\Programs\Python\Python310\python.exe")

py = ""
For Each n In nomzodlar
    If py = "" And fso.FileExists(n) Then py = n
Next
If py = "" Then py = "py"

WShell.CurrentDirectory = papka
WShell.Run """" & py & """ """ & skript & """", 0, False
