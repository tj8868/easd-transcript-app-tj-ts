Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set fso = CreateObject("Scripting.FileSystemObject")
strCurrentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Resolve Python GUI executable
strPyw = "C:\Users\Emenance-T1\AppData\Local\hermes\hermes-agent\venv\Scripts\pythonw.exe"
If Not fso.FileExists(strPyw) Then
    If fso.FileExists(strCurrentDir & "\venv\Scripts\pythonw.exe") Then
        strPyw = strCurrentDir & "\venv\Scripts\pythonw.exe"
    ElseIf fso.FileExists(strCurrentDir & "\.venv\Scripts\pythonw.exe") Then
        strPyw = strCurrentDir & "\.venv\Scripts\pythonw.exe"
    Else
        strPyw = "pythonw.exe"
    End If
End If

Set oShortcut = WshShell.CreateShortcut(strDesktop & "\EASD Meeting Minutes AI.lnk")
oShortcut.TargetPath = strPyw
oShortcut.Arguments = Chr(34) & strCurrentDir & "\app.py" & Chr(34)
oShortcut.WorkingDirectory = strCurrentDir
oShortcut.Description = "EASD Meeting Minutes AI & Live Transcription"

icoPath = strCurrentDir & "\static\favicon.ico"
If fso.FileExists(icoPath) Then
    oShortcut.IconLocation = icoPath & ",0"
End If

oShortcut.WindowStyle = 1
oShortcut.Save

WScript.Echo "Desktop shortcut 'EASD Meeting Minutes AI' updated successfully!"
