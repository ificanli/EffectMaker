function Start-EffectDemoUnityProcess {
    param(
        [Parameter(Mandatory = $true)] [string]$FilePath,
        [Parameter(Mandatory = $true)] [string[]]$ArgumentList
    )

    $previousProfile = $env:ALLUSERSPROFILE
    try {
        # UPM reads this Windows path even when no global config file exists.
        if ([string]::IsNullOrWhiteSpace($previousProfile)) {
            $commonData = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
            if ([string]::IsNullOrWhiteSpace($commonData) -or -not (Test-Path -LiteralPath $commonData -PathType Container)) {
                throw "Cannot resolve CommonApplicationData required by Unity Package Manager."
            }
            $env:ALLUSERSPROFILE = $commonData
        }
        Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WindowStyle Hidden -Wait -PassThru
    }
    finally {
        $env:ALLUSERSPROFILE = $previousProfile
    }
}
