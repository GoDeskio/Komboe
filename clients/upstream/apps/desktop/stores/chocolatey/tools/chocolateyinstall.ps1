$ErrorActionPreference = 'Stop';

$url = 'https://github.com/GoDeskio/Komboe/releases/download/desktop-v__version__/Komboe-Installer-__version__.exe'
$checksum = '__checksum__'

$packageArgs = @{
  packageName   = 'komboe'
  fileType      = 'EXE'
  softwareName  = 'Komboe'
  url           = $url
  checksum      = $checksum
  checksumType  = 'sha256'
  silentArgs    = '/S'
  validExitCodes= @(0)
}

Install-ChocolateyPackage @packageArgs
