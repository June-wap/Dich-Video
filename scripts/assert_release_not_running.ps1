$ErrorActionPreference = 'Stop'

# electron-builder empties win-unpacked before copying Electron's runtime files.
# If a launched copy holds app.asar open, this leaves a partial output directory
# (and then an app that fails before ICU initialization). Fail before packaging.
$asarPath = Join-Path $PSScriptRoot '..\release\dist\win-unpacked\resources\app.asar'
if (-not (Test-Path -LiteralPath $asarPath)) {
    exit 0
}

try {
    $stream = [System.IO.File]::Open($asarPath, 'Open', 'ReadWrite', 'None')
    $stream.Dispose()
}
catch {
    throw @"
Cannot package while $asarPath is in use.
Close every Voca Basic window (and any Voca Basic.exe process), then run the build again.
electron-builder would otherwise leave release/dist/win-unpacked only partially copied.
"@
}
