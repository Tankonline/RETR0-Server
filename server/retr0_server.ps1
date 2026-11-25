<#
Project RETR0 server package - start, stop and check the independently operated replacement server.
Everything it needs lives in this folder: services\, config\, cdn\ (asset packs), data\, python\, runtime\.

Everything listens on 127.0.0.1 only and never contacts EA infrastructure. The test emulator reaches it through
`adb reverse tcp:8780 tcp:8780` and the emulator's -dns-server 127.0.0.1 option.

Services
  dns   services\dns_logger.py                      UDP 53    logs every hostname lookup, answers NXDOMAIN
  cdn   services\recorder_server.py                 TCP 8780  serves the asset packs in cdn\ and records requests
  sync  services\local_service\retr0_local_service.py
                                                    TCP 8781  CloudCell sync (CC_Sync.php), reached through the cdn
                                                              service's proxy rule; OFF unless -WithSync

Usage (from any folder; or double-click / run retr0_server.cmd):
  powershell -ExecutionPolicy Bypass -File retr0_server.ps1 start [-WithSync] [-Lan]
  ... retr0_server.ps1 status | stop | restart [-WithSync] [-Lan]
  -Lan  LAN mode: the cdn service (TCP 8780) also listens on this PC's network addresses and serves only
        loopback and private home-network devices; it answers the RETR0 discovery broadcast on UDP 8799.
        sync (8781) and the gift admin endpoint stay 127.0.0.1-only. Windows Firewall must allow inbound
        TCP 8780 (and UDP 8799 for automatic discovery) on the Private profile.
State, PID files and logs: runtime\
#>
param(
    [Parameter(Position = 0)][ValidateSet('start', 'stop', 'status', 'restart')][string]$Action = 'status',
    [switch]$WithSync,
    [switch]$Lan,
    [string]$Rules = ''
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Py = Join-Path $Root 'python\Scripts\python.exe'
$State = Join-Path $Root 'runtime'
$CdnPort = 8780
$SyncPort = 8781
if ($Rules -eq '') {
    if ($WithSync) { $Rules = Join-Path $Root 'config\rules_cdn_sync.json' } else { $Rules = Join-Path $Root 'config\rules_cdn.json' }
}

function Get-Services {
    $svc = [ordered]@{}
    $svc['dns'] = @{ Script = 'services\dns_logger.py'; Proto = 'UDP'; Port = 53;
        Args = @('--bind', '127.0.0.1', '--port', '53', '--log', (Join-Path $State 'dns_queries.jsonl')) }
    $svc['cdn'] = @{ Script = 'services\recorder_server.py'; Proto = 'TCP'; Port = $CdnPort;
        Args = @('--port', "$CdnPort", '--rules', $Rules, '--out', (Join-Path $State 'recorder')) }
    if ($Lan) { $svc['cdn'].Args += @('--lan', '--discovery-port', '8799') }
    $svc['sync'] = @{ Script = 'services\local_service\retr0_local_service.py'; Proto = 'TCP'; Port = $SyncPort;
        Args = @('--port', "$SyncPort", '--data-dir', (Join-Path $State 'sync_data'),
                 '--seed-data', (Join-Path $Root 'data\CC_SeedData.bin'),
                 '--log-file', (Join-Path $State 'sync.log'),
                 # cloud-save uploads go through the cdn port: on a device 127.0.0.1:8780 is adb reverse or the
                 # RETR0 link; 8781 is never reachable from a device
                 '--public-base', "http://127.0.0.1:$CdnPort") }
    return $svc
}

function Get-PortOwner([string]$Proto, [int]$Port) {
    try {
        if ($Proto -eq 'UDP') {
            $e = Get-NetUDPEndpoint -LocalPort $Port -ErrorAction Stop | Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::') } | Select-Object -First 1
        } else {
            $e = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        }
        if ($null -ne $e) { return [int]$e.OwningProcess }
    } catch { }
    return 0
}

# The venv's python.exe is a launcher that starts the real interpreter as a CHILD process, and the child owns the
# port. A service is therefore the launcher's whole process tree.
function Get-Tree([int]$RootPid) {
    $all = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId)
    $tree = @($RootPid)
    $added = $true
    while ($added) {
        $added = $false
        foreach ($p in $all) {
            if (($tree -contains [int]$p.ParentProcessId) -and -not ($tree -contains [int]$p.ProcessId)) {
                $tree += [int]$p.ProcessId; $added = $true
            }
        }
    }
    return $tree
}

function Get-OurProcess([string]$Name) {
    $pidFile = Join-Path $State "$Name.pid"
    if (-not (Test-Path $pidFile)) { return $null }
    $procId = [int](Get-Content $pidFile -Raw).Trim()
    $p = Get-CimInstance Win32_Process -Filter "ProcessId = $procId" -ErrorAction SilentlyContinue
    $svc = (Get-Services)[$Name]
    if ($null -ne $p -and $p.CommandLine -like "*$(Split-Path $svc.Script -Leaf)*") { return $p }
    return $null
}

function Start-Service1([string]$Name) {
    $svc = (Get-Services)[$Name]
    $mine = Get-OurProcess $Name
    if ($null -ne $mine) { Write-Host ("{0,-5} already running (pid {1})" -f $Name, $mine.ProcessId); return }
    $owner = Get-PortOwner $svc.Proto $svc.Port
    if ($owner -ne 0) {
        $o = Get-CimInstance Win32_Process -Filter "ProcessId = $owner" -ErrorAction SilentlyContinue
        $what = ''
        if ($null -ne $o) { $what = $o.CommandLine }
        Write-Host ("{0,-5} NOT started: {1} port {2} is already used by pid {3}: {4}" -f $Name, $svc.Proto, $svc.Port, $owner, $what)
        return
    }
    $log = Join-Path $State "$Name.out.log"
    $err = Join-Path $State "$Name.err.log"
    $argList = @('-I', (Join-Path $Root $svc.Script)) + $svc.Args | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }
    $p = Start-Process -FilePath $Py -ArgumentList $argList -WorkingDirectory $Root -WindowStyle Hidden `
         -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
    Set-Content -Path (Join-Path $State "$Name.pid") -Value $p.Id -Encoding ascii
    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        if ($p.HasExited) { break }
        $owner = Get-PortOwner $svc.Proto $svc.Port
        if ($owner -ne 0 -and ((Get-Tree $p.Id) -contains $owner)) { $ok = $true; break }
    }
    if ($ok) {
        Write-Host ("{0,-5} started   pid {1}  {2} 127.0.0.1:{3}" -f $Name, $p.Id, $svc.Proto, $svc.Port)
    } else {
        Write-Host ("{0,-5} FAILED to start; see {1}" -f $Name, $err)
        if (Test-Path $err) { Get-Content $err -Tail 5 | ForEach-Object { Write-Host "      $_" } }
    }
}

function Stop-Service1([string]$Name) {
    $p = Get-OurProcess $Name
    $pidFile = Join-Path $State "$Name.pid"
    if ($null -eq $p) {
        Write-Host ("{0,-5} not running (from this script)" -f $Name)
    } else {
        $tree = Get-Tree ([int]$p.ProcessId)
        [array]::Reverse($tree)                      # children first
        foreach ($id in $tree) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
        Write-Host ("{0,-5} stopped   pid {1} (+{2} child)" -f $Name, $p.ProcessId, ($tree.Count - 1))
    }
    if (Test-Path $pidFile) { Remove-Item $pidFile -Force }
}

function Show-Status {
    $svcs = Get-Services
    foreach ($name in $svcs.Keys) {
        $svc = $svcs[$name]
        $p = Get-OurProcess $name
        $owner = Get-PortOwner $svc.Proto $svc.Port
        # (named $desc, not $state: PowerShell names ignore case and $State is the runtime folder)
        if ($null -ne $p -and $owner -ne 0 -and ((Get-Tree ([int]$p.ProcessId)) -contains $owner)) {
            $desc = "running   pid $($p.ProcessId) (listener pid $owner)"
        } elseif ($null -ne $p) {
            $desc = "process alive (pid $($p.ProcessId)) but NOT listening - see $name.err.log"
        } elseif ($owner -ne 0) {
            $desc = "port in use by another process (pid $owner), not managed by this script"
        } else {
            $desc = 'stopped'
        }
        Write-Host ("{0,-5} {1,-4} 127.0.0.1:{2,-5} {3}" -f $name, $svc.Proto, $svc.Port, $desc)
    }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$CdnPort/retr0-health" -UseBasicParsing -TimeoutSec 3
        Write-Host "cdn HTTP check: $($r.StatusCode)"
    } catch {
        $code = $null
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        if ($code) { Write-Host "cdn HTTP check: answering ($code for an unknown path, as expected)" } else { Write-Host 'cdn HTTP check: no answer' }
    }
    $l = Get-NetTCPConnection -LocalPort $CdnPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $l -and $l.LocalAddress -in @('0.0.0.0', '::')) {
        $ips = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {
            $_.IPAddress -match '^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } | ForEach-Object { $_.IPAddress })
        Write-Host ("LAN mode: ON  - devices on your network connect to {0} (port {1})" -f ($ips -join ', '), $CdnPort)
    } elseif ($null -ne $l) {
        Write-Host 'LAN mode: off (127.0.0.1 only)'
    }
    $packs = Join-Path $Root 'cdn\rr3\live'
    if (Test-Path $packs) {
        Write-Host ("packs: {0} lists in {1}" -f (Get-ChildItem $packs -Directory).Count, $packs)
    } else {
        Write-Host "packs: none found in $packs"
    }
}

New-Item -ItemType Directory -Force -Path $State | Out-Null
if (-not (Test-Path $Py)) { throw "Python not found: $Py  (create it with:  py -3 -m venv `"$Root\python`")" }
$names = @('dns', 'cdn')
if ($WithSync) { $names = @('dns', 'sync', 'cdn') }

switch ($Action) {
    'start'   { foreach ($n in $names) { Start-Service1 $n }; Write-Host ''; Show-Status }
    'stop'    { foreach ($n in @('cdn', 'sync', 'dns')) { Stop-Service1 $n } }
    'status'  { Show-Status }
    'restart' { foreach ($n in @('cdn', 'sync', 'dns')) { Stop-Service1 $n }; foreach ($n in $names) { Start-Service1 $n }; Write-Host ''; Show-Status }
}
