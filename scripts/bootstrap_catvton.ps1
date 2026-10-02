param(
    [switch]$AcceptNonCommercialLicense
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ModelRoot = Join-Path $ProjectRoot 'models'
$SourcePath = Join-Path $ModelRoot 'CatVTON'
$CheckpointPath = Join-Path $ModelRoot 'checkpoints\CatVTON'
$BaseModelPath = Join-Path $ModelRoot 'checkpoints\stable-diffusion-inpainting'
$PinnedCommit = '999bdbe81e6008a3f5749af7c1e0b0fa3d21b48e'

if (-not $AcceptNonCommercialLicense) {
    Write-Host 'CatVTON source and weights are CC BY-NC-SA 4.0 and non-commercial only.'
    Write-Host 'This downloads several gigabytes from the official GitHub and Hugging Face projects.'
    $answer = Read-Host 'Type ACCEPT to continue'
    if ($answer -ne 'ACCEPT') {
        Write-Host 'Cancelled. Nothing was downloaded.'
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path $ModelRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $CheckpointPath) | Out-Null

if (Test-Path -LiteralPath $SourcePath) {
    throw "The target source directory already exists: $SourcePath. Remove or inspect it manually."
}

git clone https://github.com/Zheng-Chong/CatVTON.git $SourcePath
git -C $SourcePath checkout --detach $PinnedCommit
python -m pip install -r (Join-Path $ProjectRoot 'requirements-catvton.txt')
python -m pip install -e $SourcePath\detectron2
python -m pip install --no-build-isolation -e "$SourcePath\detectron2\projects\DensePose"

huggingface-cli download zhengchong/CatVTON --local-dir $CheckpointPath
huggingface-cli download runwayml/stable-diffusion-inpainting --local-dir $BaseModelPath
huggingface-cli download stabilityai/sd-vae-ft-mse

Write-Host 'CatVTON setup complete. Select CatVTON in VirtualTry Settings.'
