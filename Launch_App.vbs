Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Resolve target runner script
If fso.FileExists(strDir & "\run_app.pyw") Then
    strApp = strDir & "\run_app.pyw"
Else
    strApp = strDir & "\app.py"
End If

strLocalHermes = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\pythonw.exe")
If fso.FileExists(strDir & "\.venv\Scripts\pythonw.exe") Then
    strPyw = strDir & "\.venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(strDir & "\venv\Scripts\pythonw.exe") Then
    strPyw = strDir & "\venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(strLocalHermes) Then
    strPyw = strLocalHermes
Else
    strPyw = "pythonw.exe"
End If

' Launch Python GUI runner with WindowStyle 0 (Completely hidden, NO command prompt window)
WshShell.Run Chr(34) & strPyw & Chr(34) & " " & Chr(34) & strApp & Chr(34), 0, False
