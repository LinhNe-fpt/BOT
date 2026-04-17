# Dung chung cho cai_dat.ps1 va tat_client.ps1 - khong chay truc tiep.

$script:PcmTaskName = "PCMonitorClient"

function Get-StopPasswordFromAgentEnvFile {
    param([Parameter(Mandatory)][string]$EnvFilePath)
    if (-not (Test-Path $EnvFilePath)) { return "" }
    foreach ($raw in Get-Content $EnvFilePath -Encoding utf8) {
        $line = $raw.Trim()
        if (-not $line -or $line.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        if ($key -ne "STOP_PASSWORD") { continue }
        $val = $line.Substring($eq + 1).Trim()
        if ([string]::IsNullOrWhiteSpace($val)) { return "" }
        if ($val.Length -ge 2) {
            $q = $val[0]
            if (($q -eq '"' -or $q -eq "'") -and $val.EndsWith($q)) {
                $val = $val.Substring(1, $val.Length - 2)
            }
        }
        return $val
    }
    return ""
}

function Test-StopPasswordIfSet {
    param([Parameter(Mandatory)][string]$EnvFilePath)
    $exp = Get-StopPasswordFromAgentEnvFile -EnvFilePath $EnvFilePath
    if (-not $exp) { return $true }
    Write-Host "Da dat STOP_PASSWORD trong agent.env - can nhap mat khau." -ForegroundColor Yellow
    $sec = Read-Host "Mat khau" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if ($plain -ceq $exp) { return $true }
    Write-Host "Sai mat khau." -ForegroundColor Red
    return $false
}

function Register-PcMonitorScheduledTask {
    param(
        [Parameter(Mandatory)][string]$ExePath,
        [Parameter(Mandatory)][string]$WorkDir
    )
    $taskName = $script:PcmTaskName
    $fullUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    $action = New-ScheduledTaskAction -Execute $ExePath -WorkingDirectory $WorkDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $fullUser
    $principal = New-ScheduledTaskPrincipal -UserId $fullUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $taskName `
        -Description "PC Monitor client - chay nen, gui du lieu ve may chu" `
        -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
}

function Unregister-PcMonitorScheduledTask {
    $taskName = $script:PcmTaskName
    $t = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($t) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
}
