param(
    [string]$DebugEndpoint = "http://127.0.0.1:9222",
    [string]$AppRoot = "http://127.0.0.1:8501",
    [string]$OutputRoot = "docs/images/phase7"
)

$ErrorActionPreference = "Stop"
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\$OutputRoot"))
[System.IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

$targets = Invoke-RestMethod -Uri "$DebugEndpoint/json/list"
$target = $targets |
    Where-Object { $_.type -eq "page" } |
    Select-Object -First 1
if (-not $target) {
    throw "No Chrome page target is available at $DebugEndpoint"
}

$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$socketUri = [Uri]($target.webSocketDebuggerUrl)
$socket.ConnectAsync(
    $socketUri,
    [Threading.CancellationToken]::None
).GetAwaiter().GetResult() | Out-Null
$script:messageId = 0

function Receive-CdpMessage {
    $buffer = [byte[]]::new(1048576)
    $stream = [System.IO.MemoryStream]::new()
    do {
        $segment = [ArraySegment[byte]]::new($buffer)
        $result = $socket.ReceiveAsync(
            $segment,
            [Threading.CancellationToken]::None
        ).GetAwaiter().GetResult()
        $stream.Write($buffer, 0, $result.Count)
    } while (-not $result.EndOfMessage)
    return [Text.Encoding]::UTF8.GetString($stream.ToArray())
}

function Invoke-Cdp {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [hashtable]$Parameters = @{}
    )

    $script:messageId += 1
    $requestId = $script:messageId
    $payload = @{
        id = $requestId
        method = $Method
        params = $Parameters
    } | ConvertTo-Json -Compress -Depth 20
    $bytes = [Text.Encoding]::UTF8.GetBytes($payload)
    $socket.SendAsync(
        [ArraySegment[byte]]::new($bytes),
        [Net.WebSockets.WebSocketMessageType]::Text,
        $true,
        [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult() | Out-Null

    do {
        $response = Receive-CdpMessage | ConvertFrom-Json
    } while ($response.id -ne $requestId)
    if ($response.error) {
        throw "CDP $Method failed: $($response.error.message)"
    }
    return $response.result
}

$pages = @(
    @{
        Path = "/"
        Expected = "Executive intelligence / 01"
        File = "executive-overview.png"
    },
    @{
        Path = "/Root_Cause_Explainability"
        Expected = "Explainability / 02"
        File = "root-cause-explainability.png"
    },
    @{
        Path = "/Forecast_Risk"
        Expected = "Predictive intelligence / 03"
        File = "forecast-risk.png"
    },
    @{
        Path = "/Scenario_Lab"
        Expected = "Constrained decisions / 04"
        File = "scenario-lab.png"
    },
    @{
        Path = "/Model_Reliability"
        Expected = "Reliability & governance / 05"
        File = "model-reliability.png"
    }
)

try {
    Invoke-Cdp -Method "Page.enable" | Out-Null
    Invoke-Cdp -Method "Runtime.enable" | Out-Null
    Invoke-Cdp -Method "Emulation.setDeviceMetricsOverride" -Parameters @{
        width = 1600
        height = 1200
        deviceScaleFactor = 1
        mobile = $false
    } | Out-Null

    foreach ($page in $pages) {
        $url = "$AppRoot$($page.Path)"
        Invoke-Cdp -Method "Page.navigate" -Parameters @{ url = $url } | Out-Null
        $deadline = [DateTime]::UtcNow.AddSeconds(60)
        $loaded = $false
        while ([DateTime]::UtcNow -lt $deadline) {
            Start-Sleep -Milliseconds 750
            $expectedJson = $page.Expected.ToLowerInvariant() | ConvertTo-Json -Compress
            $expression = (
                "document.body?.innerText.toLowerCase().includes($expectedJson) === true"
            )
            $evaluation = Invoke-Cdp -Method "Runtime.evaluate" -Parameters @{
                expression = $expression
                returnByValue = $true
            }
            if ($evaluation.result.value -eq $true) {
                $loaded = $true
                break
            }
        }
        if (-not $loaded) {
            throw "Page did not render expected content: $url"
        }
        Start-Sleep -Seconds 2
        $body = Invoke-Cdp -Method "Runtime.evaluate" -Parameters @{
            expression = "document.body.innerText"
            returnByValue = $true
        }
        if ($body.result.value -match "Traceback|Uncaught|Exception") {
            throw "Visible error detected at $url"
        }
        $layout = Invoke-Cdp -Method "Page.getLayoutMetrics"
        $captureHeight = [Math]::Min(
            1800,
            [Math]::Max(1200, [Math]::Ceiling($layout.cssContentSize.height))
        )
        $screenshot = Invoke-Cdp -Method "Page.captureScreenshot" -Parameters @{
            format = "png"
            fromSurface = $true
            captureBeyondViewport = $true
            clip = @{
                x = 0
                y = 0
                width = 1600
                height = $captureHeight
                scale = 1
            }
        }
        $destination = Join-Path $resolvedOutput $page.File
        [IO.File]::WriteAllBytes(
            $destination,
            [Convert]::FromBase64String($screenshot.data)
        )
        $size = (Get-Item -LiteralPath $destination).Length
        Write-Output "PASS $($page.File) $size bytes"
    }
}
finally {
    if ($socket.State -eq [Net.WebSockets.WebSocketState]::Open) {
        $socket.CloseAsync(
            [Net.WebSockets.WebSocketCloseStatus]::NormalClosure,
            "capture complete",
            [Threading.CancellationToken]::None
        ).GetAwaiter().GetResult() | Out-Null
    }
    $socket.Dispose()
}
