# AI Workflow - cai dat 1 lenh cho Windows (khong can winget, git hay ffmpeg cai tay)
#
#   irm https://raw.githubusercontent.com/BaoPV-DEV/AI_Workflow/main/install.ps1 | iex
#
# Viec script lam:
#   1. Tim Python 3.10+; neu khong co thi tai Python 3.12 tu python.org va cai cho rieng user (khong can quyen admin)
#   2. Tai code (git neu co, khong thi tai file zip) vao D:\AI_Workflow (hoac %USERPROFILE%\AI_Workflow neu khong co o D:)
#   3. Tao .venv, cai thu vien; ffmpeg di kem goi imageio-ffmpeg; trinh duyet dung Microsoft Edge co san
#   4. Tao shortcut "AI Workflow Studio" tren Desktop va mo Studio
# Chay lai lenh tren bat cu luc nao de cap nhat; thu muc workspace va settings.local.yaml duoc giu nguyen.

# Tuy chon qua bien moi truong: $env:AIWF_DIR = "E:\AI_Workflow" (thu muc cai), $env:AIWF_NOLAUNCH = "1" (khong mo Studio)
$Dir = $env:AIWF_DIR
$NoLaunch = [bool]$env:AIWF_NOLAUNCH
# Chay tu file install.ps1 nam trong repo (setup.bat / Studio.bat) => dung luon thu muc do
$Here = [bool]($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "vf.py")))
if ($Here) { $Dir = $PSScriptRoot }

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Repo = "BaoPV-DEV/AI_Workflow"
$PyVersion = "3.12.7"

function Say($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    OK  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }

# ---------- 0. thu muc cai dat
if (-not $Dir) { $Dir = if (Test-Path "D:\") { "D:\AI_Workflow" } else { Join-Path $env:USERPROFILE "AI_Workflow" } }
Say "Thu muc cai dat: $Dir"

# ---------- 1. Python
function Test-Py($exe, $extra = @()) {
    try {
        $out = & $exe @extra -c "import sys;print(sys.version_info>=(3,10))" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "True")
    } catch { return $false }
}
$Py = $null; $PyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    if (Test-Py "py" @("-3")) { $Py = "py"; $PyArgs = @("-3") }
}
if (-not $Py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*" -and (Test-Py $cmd.Source)) { $Py = $cmd.Source }
}
$Local312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (-not $Py -and (Test-Path $Local312) -and (Test-Py $Local312)) { $Py = $Local312 }
if (-not $Py) {
    Say "Chua co Python 3.10+. Dang tai Python $PyVersion (~25 MB)..."
    $inst = Join-Path $env:TEMP "python-$PyVersion-amd64.exe"
    Invoke-WebRequest "https://www.python.org/ftp/python/$PyVersion/python-$PyVersion-amd64.exe" -OutFile $inst -ErrorAction Stop
    Say "Dang cai Python (rieng cho user, khong can admin)..."
    Start-Process $inst -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0" -Wait
    if (-not (Test-Py $Local312)) { throw "Cai Python that bai. Hay cai tay tu https://www.python.org/downloads/ (tick 'Add python.exe to PATH') roi chay lai." }
    $Py = $Local312
}
Ok "Python: $Py $PyArgs"

# ---------- 2. Code
$git = Get-Command git -ErrorAction SilentlyContinue
if ($Here) {
    Ok "Dung code o thu muc hien tai"
} elseif (Test-Path (Join-Path $Dir ".git")) {
    if ($git) { Say "Cap nhat code (git pull)..."; git -C $Dir pull --ff-only | Out-Host } else { Warn "Co .git nhung khong co git: bo qua cap nhat" }
} elseif ($git -and -not (Test-Path $Dir)) {
    Say "Tai code (git clone)..."
    git clone --depth 1 "https://github.com/$Repo.git" $Dir | Out-Host
} else {
    Say "Tai code (file zip tu GitHub)..."
    $zip = Join-Path $env:TEMP "ai_workflow_main.zip"
    $tmp = Join-Path $env:TEMP "ai_workflow_unzip"
    Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/main.zip" -OutFile $zip -ErrorAction Stop
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp -Force -ErrorAction Stop
    $src = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
    New-Item -ItemType Directory -Force $Dir | Out-Null
    # chep de len, giu workspace\ va config\settings.local.yaml cua ban
    robocopy $src $Dir /E /NFL /NDL /NJH /NJS /NP /XD workspace .venv /XF settings.local.yaml | Out-Null
    Remove-Item $tmp -Recurse -Force; Remove-Item $zip -Force
}
Set-Location $Dir
Ok "Code: $Dir"

# ---------- 3. Moi truong Python
$VenvPy = Join-Path $Dir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    Say "Tao moi truong .venv..."
    & $Py @PyArgs -m venv .venv
    if (-not (Test-Path $VenvPy)) { throw "Khong tao duoc .venv" }
}
Say "Cai thu vien (lan dau mat vai phut)..."
& $VenvPy -m pip install -q --upgrade pip
& $VenvPy -m pip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install loi. Kiem tra mang roi chay lai." }
Ok "Thu vien da cai (ffmpeg di kem goi imageio-ffmpeg)"

# Trinh duyet de quay canh: uu tien Edge co san trong Windows, khong co moi tai Chromium
$edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
$local = Join-Path $Dir "config\settings.local.yaml"
if ($edge) {
    if (-not (Test-Path $local) -or -not (Select-String -Path $local -Pattern "browser_channel" -Quiet)) {
        Add-Content -Path $local -Value "visual:`r`n  browser_channel: msedge" -Encoding ASCII
    }
    Ok "Trinh duyet: Microsoft Edge"
} else {
    Say "Khong thay Edge, tai Chromium cho Playwright..."
    & $VenvPy -m playwright install chromium
}

# ---------- 4. Kiem tra, shortcut, mo Studio
& $VenvPy vf.py catalog | Out-Null
Say "Kiem tra cai dat"
& $VenvPy vf.py doctor

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "AI Workflow Studio.lnk"))
$lnk.TargetPath = Join-Path $env:SystemRoot "System32\wscript.exe"
$lnk.Arguments = '"' + (Join-Path $Dir "Studio.vbs") + '"'   # mo Studio khong hien terminal
$lnk.WorkingDirectory = $Dir
$lnk.IconLocation = "$env:SystemRoot\System32\imageres.dll,18"
$lnk.Save()
Ok "Da tao shortcut 'AI Workflow Studio' tren Desktop"

# Ket noi Claude Desktop (neu co) de chat "lam video ve ..." bang tai khoan Claude
$cd1 = Join-Path $env:APPDATA "Claude"
$cd2 = Get-ChildItem (Join-Path $env:LOCALAPPDATA "Packages") -Directory -Filter "Claude_*" -ErrorAction SilentlyContinue
if ((Test-Path $cd1) -or $cd2) {
    & $VenvPy vf.py mcp-install
    Ok "Da ket noi Claude Desktop (thoat han va mo lai Claude Desktop de dung)"
} else {
    Warn "Chua thay Claude Desktop. Cai Claude Desktop roi chay: $Dir\vf.bat mcp-install"
}
if (Get-Command claude -ErrorAction SilentlyContinue) { Ok "Claude Code: co (Studio se tu viet kich ban bang goi Claude cua ban)" }
else { Warn "Tuy chon (goi Pro/Max): cai Claude Code de Studio tu viet kich ban: irm https://claude.ai/install.ps1 | iex" }

# video mau de thu ngay
$demo = Join-Path $Dir "workspace\meo_thich_hop"
if (-not (Test-Path $demo)) { Copy-Item (Join-Path $Dir "examples\meo_thich_hop") $demo -Recurse }

Write-Host ""
Write-Host "Xong! Mo Studio bang shortcut tren Desktop, hoac: $Dir\Studio.bat" -ForegroundColor Green
Write-Host "Video mau 'meo_thich_hop' da co trong 'Video cua toi'. Bam 'Xuat video' de render." -ForegroundColor Green
if (-not $NoLaunch) { Start-Process "wscript.exe" -ArgumentList ('"' + (Join-Path $Dir "Studio.vbs") + '"') -WorkingDirectory $Dir }
