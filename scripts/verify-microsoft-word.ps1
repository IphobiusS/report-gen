param(
    [Parameter(Mandatory=$true)][string]$InputDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
# Run on an interactive Windows machine with a licensed desktop Word installation.
# Work on separate copies; update native page/index fields, save and render.
# Never enable macros or linked resources. Original files remain unchanged.
$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $InputDirectory).Path
$target = [System.IO.Path]::GetFullPath($OutputDirectory)
if ([string]::Equals($source, $target, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Use a separate output directory; source documents are preserved."
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
$files = @(Get-ChildItem -LiteralPath $source -Filter *.docx -File)
if ($files.Count -eq 0) { throw "No DOCX documents found." }
$results = @()
$word = $null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$previousUpdateLinks = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
    $previousUpdateLinks = $word.Options.UpdateLinksAtOpen
    $word.Options.UpdateLinksAtOpen = $false
    foreach ($file in $files) {
        $document = $null
        $beforeHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        try {
            # Refuse active packages and field instructions outside our exporter's vocabulary.
            $archive = [System.IO.Compression.ZipFile]::OpenRead($file.FullName)
            try {
                $expanded = ($archive.Entries | Measure-Object -Property Length -Sum).Sum
                if ($expanded -gt 134217728 -or $archive.Entries.Count -gt 2000) { throw "DOCX exceeds validation budget." }
                foreach ($entry in $archive.Entries) {
                    if ($entry.FullName -match 'vbaProject|embeddings/|activeX/') { throw "Active DOCX content is not supported." }
                    if ($entry.FullName -match '^word/.*\.xml$|\.rels$') {
                        $reader = New-Object System.IO.StreamReader($entry.Open())
                        try { $xmlText = $reader.ReadToEnd() } finally { $reader.Dispose() }
                        if ($xmlText -match '<!DOCTYPE|<!ENTITY') { throw "XML entity declarations are not permitted." }
                        $xml = New-Object System.Xml.XmlDocument
                        $xml.XmlResolver = $null
                        $xml.LoadXml($xmlText)
                        $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
                        $ns.AddNamespace('w','http://schemas.openxmlformats.org/wordprocessingml/2006/main')
                        foreach ($field in $xml.SelectNodes('//w:instrText|//w:fldSimple/@w:instr',$ns)) {
                            if ($field.InnerText.Trim() -notmatch '^(TOC|TC|PAGEREF|PAGE|NUMPAGES)\b') { throw "Unsupported field instruction." }
                        }
                        foreach ($relationship in $xml.SelectNodes('//*[local-name()="Relationship"][@TargetMode="External"]')) {
                            if ($relationship.Type -notmatch '/hyperlink$') { throw "External document resource is not allowed." }
                        }
                    }
                }
            } finally { $archive.Dispose() }
            $copy = Join-Path $target ($file.BaseName + '-word-checked.docx')
            if (Test-Path -LiteralPath $copy) { throw "Output already exists: $copy. Use an empty directory." }
            Copy-Item -LiteralPath $file.FullName -Destination $copy
            $document = $word.Documents.Open($copy, $false, $false, $false)
            foreach ($link in $document.Hyperlinks) {
                if ($link.SubAddress -and -not $document.Bookmarks.Exists($link.SubAddress)) { throw "Unresolved internal hyperlink: $($link.SubAddress)" }
            }
            $document.Repaginate()
            $updateErrors = $document.Fields.Update()
            if ($updateErrors -ne 0) { throw "Word reports a field update error at index $updateErrors." }
            foreach ($toc in $document.TablesOfContents) { $toc.Update() }
            $document.Repaginate()
            foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
            $document.Save()
            $document.Repaginate()
            $pages = $document.ComputeStatistics(2) # wdStatisticPages
            $pdf = Join-Path $target ($file.BaseName + '-word.pdf')
            $document.ExportAsFixedFormat($pdf, 17) # wdExportFormatPDF
            if ($pages -lt 1 -or -not (Test-Path -LiteralPath $pdf)) { throw "Empty Word rendering." }
            $results += @{file=$file.Name;word_version=$word.Version;pages=$pages;pdf=$pdf;status="fields_updated_and_rendered";updated_docx=$copy;index_count=$document.TablesOfContents.Count;source_sha256=$beforeHash;updated_sha256=(Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash}
        } finally {
            if ($null -ne $document) {
                $document.Close(0)
                [Runtime.InteropServices.Marshal]::FinalReleaseComObject($document) | Out-Null
            }
        }
        if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $beforeHash) {
            throw "A source DOCX changed: $($file.Name)"
        }
    }
    $record = @{platform=[Environment]::OSVersion.VersionString;results=$results;visual_acceptance="pending"}
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $target 'word-validation.json') -Encoding UTF8
} finally {
    if ($null -ne $word) {
        if ($null -ne $previousUpdateLinks) { $word.Options.UpdateLinksAtOpen = $previousUpdateLinks }
        $word.Quit(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    }
}
Write-Output "Word field updates, copy save and rendering completed. Inspect the PDF pages and compare text, commands, images and page references before acceptance."
