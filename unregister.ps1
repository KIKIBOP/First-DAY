$ErrorActionPreference='Stop'
$key='HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.chrome_media_collector.host'
$expected=Join-Path $PSScriptRoot 'com.chrome_media_collector.host.json'
if(Test-Path $key){
    $current=(Get-Item $key).GetValue('')
    if($current -eq $expected){
        Remove-Item $key -Recurse -Force
        Write-Host '已取消本便携包的注册。'
    } else {
        Write-Host '当前注册属于另一个位置，已保留。'
    }
} else { Write-Host '没有找到注册信息。' }
Write-Host '影片、设置和采集历史均已保留。请在 Chrome 中手动移除扩展。'
