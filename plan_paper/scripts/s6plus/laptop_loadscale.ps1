# laptop_loadscale.ps1 - the S10 load mechanism without kraken2, for the windows laptop (no wsl, no compiler
# installs needed: PowerShell 5.1 compiles the C# below with the .NET Framework csc that ships with windows).
#
# what S10 does on linux: up to 32 threads each pread() 64MB chunks of hash.k2d straight into a freshly
# allocated table. the cost is three things: first-touch page faults on the fresh memory, the kernel copy out
# of the file cache, and (cold) the device read. this script times each piece separately vs thread count:
#   copy_touched   memcpy into memory that is already touched  -> raw copy bandwidth ceiling (no faults)
#   copy_fresh     memcpy into fresh, never-touched memory     -> copy + first-touch faults
#   file_fresh     ReadFile from a cached file into fresh memory -> what S10 does on a warm page cache
#   direct_touched unbuffered ReadFile (no file cache) into touched memory -> device throughput vs queue depth
#
# usage (from a normal powershell window, not admin):
#   powershell -NoProfile -ExecutionPolicy Bypass -File laptop_loadscale.ps1 -SizeMB 1024 -Threads "1,2,4,8,16" -Reps 3
# keep -SizeMB under ~40% of free ram: copy modes hold two buffers of SizeMB at once.
param(
  [int]$SizeMB = 1024,
  [string]$Threads = "1,2,4,8,16",
  [int]$Reps = 3,
  [int]$ChunkMB = 4,
  [string]$Modes = "copy_touched,copy_fresh,file_fresh,direct_touched",
  [string]$Dir = "$env:TEMP\k2loadscale",
  [switch]$Keep
)

$src = @"
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

public static class K2LoadScale {
  [DllImport("kernel32.dll", SetLastError = true)] static extern IntPtr VirtualAlloc(IntPtr a, UIntPtr n, uint type, uint prot);
  [DllImport("kernel32.dll", SetLastError = true)] static extern bool VirtualFree(IntPtr a, UIntPtr n, uint type);
  [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
  static extern IntPtr CreateFileW(string name, uint access, uint share, IntPtr sec, uint disp, uint flags, IntPtr tmpl);
  [DllImport("kernel32.dll", SetLastError = true)] static extern bool ReadFile(IntPtr h, IntPtr buf, uint n, out uint got, ref NativeOverlapped ov);
  [DllImport("kernel32.dll", SetLastError = true)] static extern bool CloseHandle(IntPtr h);
  [DllImport("msvcrt.dll", CallingConvention = CallingConvention.Cdecl)] static extern IntPtr memcpy(IntPtr d, IntPtr s, UIntPtr n);
  [DllImport("msvcrt.dll", CallingConvention = CallingConvention.Cdecl)] static extern IntPtr memset(IntPtr d, int c, UIntPtr n);

  const uint MEM_COMMIT = 0x1000, MEM_RESERVE = 0x2000, MEM_RELEASE = 0x8000, PAGE_READWRITE = 0x04;
  const uint GENERIC_READ = 0x80000000, FILE_SHARE_READ = 1, OPEN_EXISTING = 3;
  const uint FILE_ATTRIBUTE_NORMAL = 0x80, FILE_FLAG_NO_BUFFERING = 0x20000000;

  public static IntPtr Alloc(long n) {
    IntPtr p = VirtualAlloc(IntPtr.Zero, new UIntPtr((ulong)n), MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (p == IntPtr.Zero) throw new Exception("VirtualAlloc failed, error " + Marshal.GetLastWin32Error());
    return p;
  }
  public static void Free(IntPtr p) { VirtualFree(p, UIntPtr.Zero, MEM_RELEASE); }
  public static void Touch(IntPtr p, long n) { memset(p, 1, new UIntPtr((ulong)n)); }

  // returns seconds for one timed pass of `mode` with `threads` workers pulling `chunk`-byte pieces
  public static double Run(string mode, string path, long bytes, int threads, long chunk, IntPtr src) {
    bool file = mode == "file_fresh" || mode == "direct_touched";
    bool fresh = mode == "copy_fresh" || mode == "file_fresh";
    IntPtr dst = Alloc(bytes);
    if (!fresh) Touch(dst, bytes);
    long next = 0; int failed = 0;
    ManualResetEvent go = new ManualResetEvent(false);
    Thread[] ws = new Thread[threads];
    for (int i = 0; i < threads; i++) {
      ws[i] = new Thread(delegate () {
        IntPtr h = IntPtr.Zero;
        if (file) {
          uint fl = mode == "direct_touched" ? FILE_FLAG_NO_BUFFERING : FILE_ATTRIBUTE_NORMAL;
          h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, IntPtr.Zero, OPEN_EXISTING, fl, IntPtr.Zero);
          if (h == new IntPtr(-1)) { Interlocked.Increment(ref failed); return; }
        }
        go.WaitOne();
        while (true) {
          long c = Interlocked.Increment(ref next) - 1;
          long off = c * chunk;
          if (off >= bytes) break;
          long len = Math.Min(chunk, bytes - off);
          IntPtr d = new IntPtr(dst.ToInt64() + off);
          if (file) {
            NativeOverlapped ov = new NativeOverlapped();
            ov.OffsetLow = (int)(off & 0xFFFFFFFF);
            ov.OffsetHigh = (int)(off >> 32);
            uint got;
            if (!ReadFile(h, d, (uint)len, out got, ref ov) || got != len) { Interlocked.Increment(ref failed); break; }
          } else {
            memcpy(d, new IntPtr(src.ToInt64() + off), new UIntPtr((ulong)len));
          }
        }
        if (file) CloseHandle(h);
      });
      ws[i].Start();
    }
    Thread.Sleep(50);  // let every worker open its handle and park on the event before the clock starts
    Stopwatch sw = Stopwatch.StartNew();
    go.Set();
    foreach (Thread w in ws) w.Join();
    sw.Stop();
    Free(dst);
    if (failed > 0) throw new Exception(mode + ": " + failed + " worker(s) failed");
    return sw.Elapsed.TotalSeconds;
  }
}
"@
Add-Type -TypeDefinition $src -Language CSharp

$bytes = [int64]$SizeMB * 1MB
$chunk = [int64]$ChunkMB * 1MB
$freeMB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1KB)
if ($freeMB -lt 2.5 * $SizeMB) { throw "only $freeMB MB free, need about $([int](2.5 * $SizeMB)) MB for -SizeMB $SizeMB. close apps or lower -SizeMB." }

$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
$dimms = (Get-CimInstance Win32_PhysicalMemory | ForEach-Object { "$($_.DeviceLocator)/$($_.BankLabel) $([int]($_.Capacity / 1GB))GB@$($_.ConfiguredClockSpeed)" }) -join "; "
Write-Host "cpu: $cpu | dimms: $dimms | free: $freeMB MB | size: $SizeMB MB | chunk: $ChunkMB MB | reps: $Reps"

New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$path = Join-Path $Dir "loadscale_$SizeMB.bin"
if (-not (Test-Path $path) -or (Get-Item $path).Length -ne $bytes) {
  Write-Host "writing $SizeMB MB test file to $path"
  $buf = New-Object byte[] (1MB); (New-Object System.Random 42).NextBytes($buf)
  $fs = [System.IO.File]::Create($path)
  for ($i = 0; $i -lt $SizeMB; $i++) { $fs.Write($buf, 0, $buf.Length) }
  $fs.Close()
}
# warm the windows file cache so file_fresh measures a cached-file copy, like the luna runs
$fs = [System.IO.File]::OpenRead($path); $buf = New-Object byte[] (8MB)
while ($fs.Read($buf, 0, $buf.Length) -gt 0) { }; $fs.Close()

$srcBuf = [K2LoadScale]::Alloc($bytes); [K2LoadScale]::Touch($srcBuf, $bytes)
$rows = @()
foreach ($m in $Modes.Split(",")) {
  $base = $null
  foreach ($t in ($Threads.Split(",") | ForEach-Object { [int]$_ })) {
    $times = @(); for ($r = 0; $r -lt $Reps; $r++) { $times += [K2LoadScale]::Run($m, $path, $bytes, $t, $chunk, $srcBuf) }
    $sorted = $times | Sort-Object; $med = $sorted[[int][math]::Floor(($sorted.Count - 1) / 2)]
    if ($null -eq $base) { $base = $med }
    $rows += [pscustomobject]@{ mode = $m; threads = $t; median_s = [math]::Round($med, 4); GBps = [math]::Round($bytes / 1e9 / $med, 2);
                                vs_1st = [math]::Round($base / $med, 2); min_s = [math]::Round($sorted[0], 4); max_s = [math]::Round($sorted[-1], 4) }
  }
}
[K2LoadScale]::Free($srcBuf)
$rows | Format-Table -AutoSize
$csv = Join-Path $Dir ("loadscale_{0}.csv" -f (Get-Date -Format "yyyy-MM-dd_HHmm"))
$rows | Export-Csv -NoTypeInformation -Path $csv
Write-Host "wrote $csv"
if (-not $Keep) { Remove-Item $path }
