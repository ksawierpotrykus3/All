$base = 'c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core\dane_badania'
New-Item -ItemType Directory -Force -Path "$base\archiwum\it" | Out-Null
New-Item -ItemType Directory -Force -Path "$base\archiwum\serwisy" | Out-Null

$itIds = @('143272','143733','143271','143273','143274','143280','143290','143318','143335','143338','143373','143425','143543','143650','143767','143823','143979','143275','143308','143310','143323','143344','143397','143429','143432','143454','143465','143507','143548','143562','143618','143652','143681','143690','143698','143721','143763')
$serIds = @('143355','143654','143589','143279','143413','143824','143891')

foreach ($id in $itIds) {
    Get-ChildItem -Path "$base\it" -Directory -Filter "$id*" | ForEach-Object {
        Move-Item -Path $_.FullName -Destination "$base\archiwum\it" -Force
    }
}
foreach ($id in $serIds) {
    Get-ChildItem -Path "$base\serwisy" -Directory -Filter "$id*" | ForEach-Object {
        Move-Item -Path $_.FullName -Destination "$base\archiwum\serwisy" -Force
    }
}
Write-Output 'Przeniesiono do archiwum.'