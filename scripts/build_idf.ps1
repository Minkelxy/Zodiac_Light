[CmdletBinding()]
param(
    [string]$IdfPath,
    [string]$IdfPython,
    [string]$ToolsPath,
    [switch]$Menuconfig,
    [ValidateRange(-1, 4)][int]$Mode = -1,
    [ValidateSet('twinkle', 'flow', 'ripple', 'breath', 'aurora', 'sparkle', 'graph_wave', 'draw', 'meteor')][string]$Effect,
    [ValidateRange(1, 16)][int]$Jobs = 4
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
if ($Effect) {
    if ($Mode -ge 0 -and $Mode -ne 4) { throw '-Effect requires Mode 4 and cannot be combined with Mode 0..3.' }
    $Mode = 4
}
$savedEnvironment = @{}
foreach ($name in @('PATH', 'IDF_PATH', 'IDF_TOOLS_PATH', 'IDF_PYTHON_ENV_PATH', 'IDF_COMPONENT_MANAGER', 'PYTHONUTF8')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    # Selected records may be missing or empty. Check all usable installations
    # before falling back to an explicit/environment configuration.
    $sdkCandidates = @()
    foreach ($candidate in @((Join-Path $env:USERPROFILE '.espressif\esp_idf.json'), 'C:\Espressif\esp_idf.json')) {
        if (-not (Test-Path -LiteralPath $candidate)) { continue }
        try { $installation = Get-Content -LiteralPath $candidate -Raw | ConvertFrom-Json }
        catch { Write-Warning "Ignoring invalid ESP-IDF installer configuration: $candidate"; continue }
        if (-not $installation.idfInstalled) { continue }
        $records = @()
        if ($installation.idfSelectedId) {
            $selectedProperty = $installation.idfInstalled.PSObject.Properties[[string]$installation.idfSelectedId]
            if ($selectedProperty -and $selectedProperty.Value) { $records += $selectedProperty.Value }
        }
        $records += @($installation.idfInstalled.PSObject.Properties.Value)
        foreach ($record in $records) {
            if (-not $record -or -not ($record.path -is [string]) -or [string]::IsNullOrWhiteSpace($record.path)) { continue }
            if ($IdfPath -and $record.path.TrimEnd('\', '/') -ne $IdfPath.TrimEnd('\', '/')) { continue }
            $recordPython = if ($IdfPython) { $IdfPython } else { $record.python }
            $recordTools = if ($ToolsPath) { $ToolsPath } else { $installation.idfToolsPath }
            $sdkCandidates += [pscustomobject]@{ Path = $record.path; Python = $recordPython; Tools = $recordTools }
        }
    }
    $sdkCandidates += [pscustomobject]@{
        Path = $(if ($IdfPath) { $IdfPath } else { $env:IDF_PATH })
        Python = $(if ($IdfPython) { $IdfPython } elseif ($env:IDF_PYTHON_ENV_PATH) { Join-Path $env:IDF_PYTHON_ENV_PATH 'Scripts\python.exe' })
        Tools = $(if ($ToolsPath) { $ToolsPath } else { $env:IDF_TOOLS_PATH })
    }
    $resolved = $false
    $seen = @{}
    foreach ($sdk in $sdkCandidates) {
        if ([string]::IsNullOrWhiteSpace($sdk.Path) -or [string]::IsNullOrWhiteSpace($sdk.Python) -or [string]::IsNullOrWhiteSpace($sdk.Tools)) { continue }
        $candidateKey = $sdk.Path + '|' + $sdk.Python + '|' + $sdk.Tools
        if ($seen.ContainsKey($candidateKey)) { continue }
        $seen[$candidateKey] = $true
        if (-not (Test-Path -LiteralPath (Join-Path $sdk.Path 'tools\idf_tools.py')) -or
            -not (Test-Path -LiteralPath $sdk.Python -PathType Leaf) -or
            -not (Test-Path -LiteralPath $sdk.Tools -PathType Container)) { continue }
        $idfSdkPath = (Resolve-Path -LiteralPath $sdk.Path).Path
        $idfPythonPath = (Resolve-Path -LiteralPath $sdk.Python).Path
        $idfToolsRoot = (Resolve-Path -LiteralPath $sdk.Tools).Path
        $env:PATH = $savedEnvironment['PATH']
        $env:IDF_PATH = $idfSdkPath
        $env:IDF_TOOLS_PATH = $idfToolsRoot
        $env:IDF_PYTHON_ENV_PATH = Split-Path (Split-Path $idfPythonPath -Parent) -Parent
        $env:IDF_COMPONENT_MANAGER = '0'
        $env:PYTHONUTF8 = '1'
        # Windows PowerShell can promote redirected native stderr to an error
        # under Stop. Inspect the exit status instead so another SDK can work.
        $previousErrorAction = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $exports = & $idfPythonPath (Join-Path $idfSdkPath 'tools\idf_tools.py') export --format key-value 2>&1
            $exportExitCode = $LASTEXITCODE
        } finally { $ErrorActionPreference = $previousErrorAction }
        if ($exportExitCode -ne 0) { Write-Warning "ESP-IDF tool export failed for $idfSdkPath; trying another installation."; continue }
        foreach ($line in $exports) {
            if ($line -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { continue }
            $name, $value = $Matches[1], $Matches[2]
            if (-not $savedEnvironment.ContainsKey($name)) {
                $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
            }
            if ($name -eq 'PATH') { $value = $value.Replace('%PATH%', $env:PATH).Replace('$PATH', $env:PATH) }
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
        $cmake = Get-Command cmake -ErrorAction SilentlyContinue
        $ninja = Get-Command ninja -ErrorAction SilentlyContinue
        if (-not $cmake -or -not $ninja) { Write-Warning "CMake/Ninja unavailable for $idfSdkPath; trying another installation."; continue }
        $cmakePath, $ninjaPath = $cmake.Source, $ninja.Source
        $resolved = $true
        break
    }
    if (-not $resolved) { throw 'No usable ESP-IDF installation found. Specify -IdfPath, -IdfPython and -ToolsPath.' }

    # idf.py realpath expands junctions. Direct CMake preserves this ASCII alias.
    # Modes share the project/SDK cache so Mode=-1 retains menuconfig choices.
    $hashInput = [Text.Encoding]::UTF8.GetBytes($projectRoot + '|' + $idfSdkPath)
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { $fingerprint = ([BitConverter]::ToString($hasher.ComputeHash($hashInput))).Replace('-', '').Substring(0, 12) }
    finally { $hasher.Dispose() }
    $cacheRoot = Join-Path ([IO.Path]::GetTempPath()) ('constellation-lamp-idf-' + $fingerprint)
    if ($cacheRoot -match '[^\x00-\x7F]') { throw 'Build cache path must use ASCII. Set TEMP to an ASCII directory for this command.' }
    New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
    $sourceAlias = Join-Path $cacheRoot 'workspace'
    if (Test-Path -LiteralPath $sourceAlias) {
        $link = Get-Item -LiteralPath $sourceAlias -Force
        $linkTargets = @($link.Target)
        if ($link.LinkType -ne 'Junction' -or $linkTargets.Count -ne 1 -or $linkTargets[0].TrimEnd('\') -ne $projectRoot.TrimEnd('\')) {
            throw "Existing source alias is not the expected project junction: $sourceAlias"
        }
    } else {
        New-Item -ItemType Junction -Path $sourceAlias -Target $projectRoot | Out-Null
    }
    $source = Join-Path $sourceAlias 'firmware-idf'
    $buildDirectory = Join-Path $cacheRoot 'build'
    $generatedDirectory = Join-Path $cacheRoot 'inputs'
    $sdkconfigPath = Join-Path $buildDirectory 'sdkconfig'
    $prepareScript = Join-Path $sourceAlias 'scripts\prepare_firmware.py'
    New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
    $prepareArgs = @($prepareScript, 'prepare', '--project-root', $sourceAlias,
                     '--generated-dir', $generatedDirectory, '--sdkconfig', $sdkconfigPath, '--mode', $Mode)
    if ($Effect) { $prepareArgs += @('--effect', $Effect) }
    $prepared = & $idfPythonPath @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Firmware scene/hardware validation failed; existing generated inputs were preserved.' }
    $scene = $prepared | ConvertFrom-Json
    $outputDirectory = Join-Path $projectRoot 'build\esp-idf'
    if ($scene.actual_mode -gt 0) { $outputDirectory = Join-Path $outputDirectory ('mode-' + $scene.actual_mode) }
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    $defaults = (Join-Path $source 'sdkconfig.defaults') + ';' + (Join-Path $generatedDirectory 'derived.sdkconfig.defaults')
    $logFile = Join-Path $outputDirectory 'build.log'
    Write-Output "SDK: $idfSdkPath"
    Write-Output "Build cache: $buildDirectory"
    Write-Output "Scene: $($scene.led_count) LEDs, $($scene.scene_sha256), mode $($scene.actual_mode), $($scene.actual_fps) FPS"
    $configureArgs = @('-S', $source, '-B', $buildDirectory, '-G', 'Ninja', '-DIDF_TARGET=esp32',
                       ('-DPYTHON=' + $idfPythonPath), ('-DCMAKE_MAKE_PROGRAM=' + $ninjaPath),
                       ('-DSDKCONFIG=' + $sdkconfigPath), ('-DSDKCONFIG_DEFAULTS=' + $defaults),
                       ('-DCLP_GENERATED_DIR=' + $generatedDirectory))
    & $cmakePath @configureArgs 2>&1 | Tee-Object -FilePath $logFile
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF CMake configuration failed; see $logFile" }
    if ($Menuconfig) {
        & $cmakePath --build $buildDirectory --target menuconfig
        if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF menuconfig failed.' }
        # Scene and hardware.json remain authoritative. Preserve all unrelated
        # choices but synchronize derived settings again after menuconfig.
        $prepared = & $idfPythonPath @prepareArgs
        if ($LASTEXITCODE -ne 0) { throw 'Firmware input synchronization failed after menuconfig.' }
        $scene = $prepared | ConvertFrom-Json
        $outputDirectory = Join-Path $projectRoot 'build\esp-idf'
        if ($scene.actual_mode -gt 0) {
            $outputDirectory = Join-Path $outputDirectory ('mode-' + $scene.actual_mode)
        }
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
        $logFile = Join-Path $outputDirectory 'build.log'
        & $cmakePath @configureArgs 2>&1 | Tee-Object -FilePath $logFile -Append
        if ($LASTEXITCODE -ne 0) { throw 'ESP-IDF configuration failed after menuconfig.' }
    }
    & $cmakePath --build $buildDirectory --parallel $Jobs 2>&1 | Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) { throw "ESP-IDF build failed; see $logFile" }

    # Keep convenient artifacts in the project; the authoritative source stays here.
    if (-not (Test-Path -LiteralPath (Join-Path $buildDirectory 'constellation_lamp_idf.bin') -PathType Leaf)) {
        throw 'Build completed without the expected firmware binary; previous artifacts were preserved.'
    }
    foreach ($relative in @('constellation_lamp_idf.bin', 'constellation_lamp_idf.elf', 'constellation_lamp_idf.map',
                           'flasher_args.json', 'flash_args', 'sdkconfig', 'project_description.json',
                           'bootloader\bootloader.bin', 'partition_table\partition-table.bin')) {
        $built = Join-Path $buildDirectory $relative
        if (-not (Test-Path -LiteralPath $built)) { continue }
        $destination = Join-Path $outputDirectory $relative
        New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $built -Destination $destination -Force
    }
    $finalizeArgs = @($prepareScript, 'finalize', '--project-root', $sourceAlias,
        '--generated-dir', $generatedDirectory, '--sdkconfig', $sdkconfigPath,
        '--artifact-dir', $outputDirectory, '--sdk-path', $idfSdkPath, '--python-path', $idfPythonPath,
        '--source-alias', $source, '--build-directory', $buildDirectory)
    & $idfPythonPath @finalizeArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Built firmware validation failed; no new hardware profile was published.' }
    Write-Output "Firmware artifacts: $outputDirectory"
} finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
}
