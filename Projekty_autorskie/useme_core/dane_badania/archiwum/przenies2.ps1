$base = 'c:\Users\Ksawier\Pictures\Screenshots\Projekty_autorskie\useme_core\dane_badania'
$ids = @('143747','143750','143916','143994','143665','144045')

foreach ($id in $ids) {
    Get-ChildItem -Path "$base\it", "$base\serwisy" -Directory -Filter "$id*" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.FullName -like '*\it\*') { $dest = 'it' } else { $dest = 'serwisy' }
        Move-Item -Path $_.FullName -Destination "$base\archiwum\$dest" -Force
    }
}
Write-Output 'Dopisano brakujace oferty.'