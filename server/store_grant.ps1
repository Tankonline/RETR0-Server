# Replaced by client.ps1 (2026-11-19): the RETR0 client APK contains the store grants and the built-in
# local-server redirect. This wrapper keeps the old commands working.
param([Parameter(Mandatory = $true)][ValidateSet("status", "apply", "restore", "install-fresh")][string]$Command)
& (Join-Path $PSScriptRoot "client.ps1") $Command
