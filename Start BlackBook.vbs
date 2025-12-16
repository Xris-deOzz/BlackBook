Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\ossow\OneDrive\PerunsBlackBook"
WshShell.Run "cmd /c BlackBook.bat", 1, False
