Set WshShell = CreateObject("WScript.Shell")
strDesktop = WshShell.SpecialFolders("Desktop")
Set fso = CreateObject("Scripting.FileSystemObject")
strCurrentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Resolve target runner script
If fso.FileExists(strCurrentDir & "\run_app.pyw") Then
    strApp = strCurrentDir & "\run_app.pyw"
Else
    strApp = strCurrentDir & "\app.py"
End If

strLocalHermes = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\pythonw.exe")
If fso.FileExists(strCurrentDir & "\.venv\Scripts\pythonw.exe") Then
    strPyw = strCurrentDir & "\.venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(strCurrentDir & "\venv\Scripts\pythonw.exe") Then
    strPyw = strCurrentDir & "\venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(strLocalHermes) Then
    strPyw = strLocalHermes
Else
    strPyw = "pythonw.exe"
End If

Set oShortcut = WshShell.CreateShortcut(strDesktop & "\EASD Meeting Minutes AI.lnk")
oShortcut.TargetPath = strPyw
oShortcut.Arguments = Chr(34) & strApp & Chr(34)
oShortcut.WorkingDirectory = strCurrentDir
oShortcut.Description = "EASD Meeting Minutes AI & Live Transcription"

icoPath = strCurrentDir & "\static\favicon.ico"
If fso.FileExists(icoPath) Then
    oShortcut.IconLocation = icoPath & ",0"
End If

oShortcut.WindowStyle = 1
oShortcut.Save

WScript.Echo "Desktop shortcut 'EASD Meeting Minutes AI' updated successfully!"
