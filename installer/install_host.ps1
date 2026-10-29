param([string]$ExtensionId, [string]$Root)
$ErrorActionPreference = 'Stop'
if (-not $ExtensionId) { $ExtensionId = Read-Host 'Chrome extension ID (chrome://extensions)' }
if ($ExtensionId -cnotmatch '^[a-p]{32}$') { throw 'Invalid extension ID: expected 32 lowercase a-p characters' }
$packageRoot = Split-Path $PSScriptRoot -Parent
$exe = Join-Path $packageRoot 'dist\MediaCollectorHost.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'Missing dist\MediaCollectorHost.exe. Run build_exe.bat on Windows first, or obtain a prebuilt distribution.' }
$dest = Join-Path $env:LOCALAPPDATA 'ChromeMediaCollector'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
$target = Join-Path $dest 'MediaCollectorHost.exe'
Copy-Item -LiteralPath $exe -Destination $target -Force
if (-not $Root) { $Root = Read-Host 'Absolute local save root (blank = Videos\CollectedMovies)' }
if (-not $Root) { $Root = Join-Path ([Environment]::GetFolderPath('MyVideos')) 'CollectedMovies' }
if ($Root -notmatch '^[A-Za-z]:\\' -or $Root.Length -gt 110) { throw 'Use an absolute local drive path, maximum 110 characters' }
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$configPath = Join-Path $dest 'settings.json'
$config = @{}
if (Test-Path -LiteralPath $configPath) {
    $obj = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($p in $obj.PSObject.Properties) { $config[$p.Name] = $p.Value }
}
$config['root'] = $Root
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json), $utf8)
$manifestPath = Join-Path $dest 'com.chrome_media_collector.host.json'
$manifest = @{
    name = 'com.chrome_media_collector.host'
    description = 'Chrome Media Collector Native Messaging Host'
    path = $target
    type = 'stdio'
    allowed_origins = @("chrome-extension://$ExtensionId/")
}
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json), $utf8)
$key = 'HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.chrome_media_collector.host'
New-Item -Path $key -Force | Out-Null
Set-Item -Path $key -Value $manifestPath
Write-Host 'Installed for current user. Restart Chrome and open extension settings to verify native communication.'
Write-Host 'Use Detect BitComet in extension settings; associate Magnet with BitComet in Windows default apps.'
# Native stdio smoke test. This does not launch or submit a magnet.
$start = New-Object Diagnostics.ProcessStartInfo
$start.FileName = $target
$start.UseShellExecute = $false
$start.RedirectStandardInput = $true
$start.RedirectStandardOutput = $true
$start.CreateNoWindow = $true
$p = [Diagnostics.Process]::Start($start)
try {
    $payload = [Text.Encoding]::UTF8.GetBytes('{"type":"get_status"}')
    $p.StandardInput.BaseStream.Write([BitConverter]::GetBytes([uint32]$payload.Length), 0, 4)
    $p.StandardInput.BaseStream.Write($payload, 0, $payload.Length)
    $p.StandardInput.BaseStream.Flush()
    $bytes = New-Object IO.MemoryStream
    $pending = $p.StandardOutput.BaseStream.CopyToAsync($bytes)
    $p.StandardInput.Close()
    if (-not $p.WaitForExit(15000)) { $p.Kill(); throw 'Native protocol test timed out' }
    $pending.GetAwaiter().GetResult()
    $output = $bytes.ToArray()
    if ($output.Length -lt 4) { throw 'Native response header missing' }
    $length = [BitConverter]::ToUInt32($output, 0)
    if ($length -gt 900000 -or $output.Length -ne ($length + 4)) { throw 'Invalid native response frame' }
    $reply = [Text.Encoding]::UTF8.GetString($output, 4, [int]$length) | ConvertFrom-Json
    if (-not $reply.ok) { throw 'Native host smoke test failed' }
    Write-Host ($reply.data.bitcomet | ConvertTo-Json -Depth 4)
    Write-Host 'Native process protocol smoke test passed. Browser-to-host test still requires Chrome settings page.'
} finally { $p.Dispose() }
