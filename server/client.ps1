# RETR0 client: the game on the test emulator, connected to this server with no Frida and no time limit.
#
#   .\client.ps1 status         which APK the emulator's game is running
#   .\client.ps1 apply          swap the installed APK for the RETR0 client in place (keeps all game data)
#   .\client.ps1 restore        swap the original 14.0.1 APK back in place (keeps all game data)
#   .\client.ps1 install-fresh  NEW INSTALL ONLY: uninstall, then install the debug-signed RETR0 client
#                               (uninstalling deletes the game's data and downloads; asks first)
#   .\client.ps1 play           forward port 8780 to this PC and start the game (needs the RETR0 client
#                               and the server: retr0_server.cmd start -WithSync)
#
# The RETR0 client is the original 14.0.1 APK plus (1) the store preservation grants (OVERVIEW.md section 8)
# and (2) a built-in redirect: every CloudCell / asset-CDN request goes to http://127.0.0.1:8780 on the
# emulator, which `adb reverse` forwards to this server (OVERVIEW.md section 9). Other hosts are untouched.
# apply/restore need root on the emulator (Google APIs image): they copy the APK over base.apk and keep its
# owner, mode, SELinux label and timestamp, then let Android re-optimise the app's code.
param([Parameter(Mandatory = $true)][ValidateSet("status", "apply", "restore", "install-fresh", "play")][string]$Command)

$ErrorActionPreference = "Stop"
$Pkg = "com.ea.games.r3_row"
$Port = 8780
$ApkDir = Join-Path $PSScriptRoot "client\apk"
$Client = "rr3_14.0.1_retr0_client.apk"
$ClientSigned = "rr3_14.0.1_retr0_client_signed.apk"
$Original = "rr3_14.0.1_original.apk"

function Get-Sha([string]$path) { return (Get-FileHash $path -Algorithm SHA256).Hash.ToLower() }

function Get-Known {
    $k = @{}
    foreach ($f in Get-ChildItem $ApkDir -Filter *.apk) { $k[(Get-Sha $f.FullName)] = $f.Name }
    return $k
}

function Get-BaseApk {
    $p = (adb shell pm path $Pkg) | Select-Object -First 1
    if (-not $p) { throw "$Pkg is not installed on the emulator" }
    return $p.Trim().Substring(8)
}

function Get-DeviceSha([string]$path) {
    return ((adb shell "su 0 sha256sum '$path'") -split "\s+")[0]
}

function Set-DeviceApk([string]$localName) {
    $local = Join-Path $ApkDir $localName
    if (-not (Test-Path $local)) { throw "missing $local" }
    $base = Get-BaseApk
    $mtime = (adb shell "su 0 stat -c %Y '$base'").Trim()
    adb shell am force-stop $Pkg
    adb push $local /data/local/tmp/retr0_swap.apk | Out-Host
    adb shell "su 0 sh -c 'cp /data/local/tmp/retr0_swap.apk ""$base"" && chown system:system ""$base"" && chmod 644 ""$base"" && restorecon ""$base"" && touch -d @$mtime ""$base"" && rm /data/local/tmp/retr0_swap.apk'" | Out-Null
    $sha = Get-DeviceSha $base
    if ($sha -ne (Get-Sha $local)) { throw "copy check failed: device $sha" }
    # The app's code changed, so drop the old compiled code; Android recompiles it from the new APK.
    adb shell cmd package compile -f -m verify $Pkg | Out-Host
    Write-Host "installed in place: $localName"
}

switch ($Command) {
    "status" {
        $base = Get-BaseApk
        $sha = Get-DeviceSha $base
        $name = (Get-Known)[$sha]; if (-not $name) { $name = "unknown APK" }
        Write-Host "$base"
        Write-Host "sha256 $sha -> $name"
    }
    "apply" { Set-DeviceApk $Client }
    "restore" { Set-DeviceApk $Original }
    "install-fresh" {
        $ans = Read-Host "This UNINSTALLS $Pkg and deletes its data and downloaded assets. Type YES to continue"
        if ($ans -ne "YES") { Write-Host "cancelled"; break }
        adb uninstall $Pkg | Out-Host
        adb install (Join-Path $ApkDir $ClientSigned) | Out-Host
        Write-Host "Installed. Continue with the fresh-install steps in OVERVIEW.md section 5.3."
    }
    "play" {
        $name = (Get-Known)[(Get-DeviceSha (Get-BaseApk))]
        if ($name -notlike "rr3_14.0.1_retr0_client*") {
            Write-Host "The emulator is not running the RETR0 client ($name); run .\client.ps1 apply first."
            exit 1
        }
        adb reverse "tcp:$Port" "tcp:$Port" | Out-Null
        adb shell am force-stop $Pkg
        adb shell monkey -p $Pkg -c android.intent.category.LAUNCHER 1 | Out-Null
        Write-Host "Game started; it talks to this server on port $Port until you close it."
    }
}
