param([ValidateRange(1,12)][int]$Hours = 10)
$signature = @'
using System;
using System.Runtime.InteropServices;
public static class AwakeState {
  [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
  public static extern uint SetThreadExecutionState(uint flags);
}
'@
Add-Type -TypeDefinition $signature
$continuous = 0x80000000
$systemRequired = 0x00000001
[AwakeState]::SetThreadExecutionState($continuous -bor $systemRequired) | Out-Null
try { Start-Sleep -Seconds ($Hours * 3600) }
finally { [AwakeState]::SetThreadExecutionState($continuous) | Out-Null }
