' Mo AI Workflow Studio KHONG hien cua so terminal (pythonw.exe).
' Lan dau (chua cai dat) se goi Studio.bat de cai, cua so cai dat can hien de theo doi.
' Can xem log/loi: mo .cache\studio.log, hoac chay "Studio.bat debug".
Option Explicit
Dim sh, fs, dir, pyw
Set sh = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
dir = fs.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
pyw = dir & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(pyw) Then
  sh.Run """" & dir & "\Studio.bat"" install", 1, False
  WScript.Quit
End If
sh.Environment("Process")("VF_HIDDEN") = "1"
' Studio tu tat ban cu dang chiem cong 8765 roi mo trinh duyet; dong tab Studio la tu tat.
sh.Run """" & pyw & """ """ & dir & "\vf.py"" studio", 0, False
