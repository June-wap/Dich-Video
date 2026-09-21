' Tool Dich Cho Khach (17/09) - launcher AN cho shortcut Start Menu/Desktop.
'
' Vi sao can file nay: "run_backend.ps1" (cach chay chinh thuc) khi bam thang
' se mo mot cua so PowerShell mau den dung sau cua so app that (pywebview) -
' trong khong giong mot app Windows binh thuong, de gay hieu lam la loi. File
' .vbs nay chi lam DUNG mot viec: goi lai chinh "run_backend.ps1" nhung an
' han cua so PowerShell (WindowStyle = 0) - cua so app that (pywebview) VAN
' hien binh thuong, khong doi gi ca ve chuc nang.
'
' Khong tu doan duong dan cung (vi du "D:\...") - tu tinh theo vi tri THAT
' cua chinh file .vbs nay (scripts\) de van dung neu sau nay ban di chuyen
' hoac cai vao thu muc khac.
'
' Log: vi cua so PowerShell bi an nen ban se KHONG thay duoc thong bao loi
' truc tiep (vi du "Official Python 3.12 unavailable") neu co su co luc khoi
' dong - toan bo output duoc ghi lai vao ".runtime\launch.log" (cung thu muc
' voi file token phien lam viec) de tu kiem tra khi can, xem huong dan chay
' chuong trinh trong tai lieu du an.

Dim objFSO, objShell, scriptDir, projectRoot, runtimeDir, logFile, psScript, psCommand

Set objFSO = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("WScript.Shell")

scriptDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
projectRoot = objFSO.GetParentFolderName(scriptDir)
runtimeDir = projectRoot & "\.runtime"

If Not objFSO.FolderExists(runtimeDir) Then
    objFSO.CreateFolder(runtimeDir)
End If

logFile = runtimeDir & "\launch.log"
psScript = scriptDir & "\run_backend.ps1"

' Start-Transcript ghi lai toan bo output (ca loi) cua run_backend.ps1 vao
' logFile, ghi noi tiep (-Append) chu khong ghi de moi lan mo app, de con
' xem lai lich su vai lan chay gan nhat khi debug.
psCommand = "& { Start-Transcript -Path '" & logFile & "' -Append | Out-Null; " & _
            "try { & '" & psScript & "' } finally { Stop-Transcript | Out-Null } }"

objShell.CurrentDirectory = projectRoot
objShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command """ & psCommand & """", 0, False
