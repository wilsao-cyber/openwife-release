Set WshShell = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
projDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopPath = WshShell.SpecialFolders("Desktop")
Set shortcut = WshShell.CreateShortcut(desktopPath & "\AI Wife.lnk")
shortcut.TargetPath = projDir & "\AI Wife.bat"
shortcut.WorkingDirectory = projDir
shortcut.IconLocation = projDir & "\ai_wife.ico"
shortcut.Description = "AI Wife App"
shortcut.WindowStyle = 1
shortcut.Save
WScript.Echo "Desktop shortcut created!"
