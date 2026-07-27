$Action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-e bash -c `"cd /mnt/c/dev/trade/p/momentum-v2 && ./sync_from_vps.sh`""
$Trigger = New-ScheduledTaskTrigger -Daily -At "11:15"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "Momentum-V2-Sync" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Sync from VPS to local Windows workspace" -Force
Write-Host "✅ Tarea programada 'Momentum-V2-Sync' creada exitosamente para correr a las 11:15 AM."
