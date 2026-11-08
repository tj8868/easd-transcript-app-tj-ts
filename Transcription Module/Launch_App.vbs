' Windows Silent 1-Click Launcher (Zero Console Window)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)
strParent = fso.GetParentFolderName(strPath)

strPyw = "pythonw"
If fso.FileExists(strParent & "\.venv\Scripts\pythonw.exe") Then
    strPyw = """" & strParent & "\.venv\Scripts\pythonw.exe"""
ElseIf fso.FileExists(strPath & "\.venv\Scripts\pythonw.exe") Then
    strPyw = """" & strPath & "\.venv\Scripts\pythonw.exe"""
End If

WshShell.CurrentDirectory = strPath
WshShell.Run strPyw & " """ & strPath & "\run_app.pyw""", 0, False
