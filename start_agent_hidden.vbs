Option Explicit

Dim shell
Dim fso
Dim scriptDir
Dim batchPath

Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
batchPath = fso.BuildPath(scriptDir, "start_agent.bat")

shell.Run """" & batchPath & """", 0, False

Set fso = Nothing
Set shell = Nothing
