Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Full path to app.py
strApp = strDir & "\app.py"

' Resolve Python virtual environment
strPyw = "C:\Users\Emenance-T1\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
If Not fso.FileExists(strPyw) Then
    If fso.FileExists(strDir & "\venv\Scripts\pythonw.exe") Then
        strPyw = strDir & "\venv\Scripts\pythonw.exe"
    ElseIf fso.FileExists(strDir & "\.venv\Scripts\pythonw.exe") Then
        strPyw = strDir & "\.venv\Scripts\pythonw.exe"
    Else
        strPyw = "pythonw.exe"
    End If
End If

' Launch Python GUI runner with WindowStyle 0 (Completely hidden, NO command prompt window)
WshShell.Run Chr(34) & strPyw & Chr(34) & " " & Chr(34) & strApp & Chr(34), 0, False
