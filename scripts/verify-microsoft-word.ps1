param(
    [Parameter(Mandatory=$true)][string]$InputDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$ExpectedSourceReceipt
)
function Test-ReportGenWordFieldInstruction {
    param([string]$Instruction)
    $instructionText = $Instruction.Trim()
    if ($instructionText -match '^(TOC|TC|PAGEREF|PAGE|NUMPAGES)\b') { return $true }
    # Only the decimal sequence emitted by exporters/numbering.py is allowed.
    # Do not enable arbitrary SEQ switches, names or nested field instructions.
    $sequence = [regex]::Match($instructionText, '\ASEQ RGList([1-9][0-9]{0,9}) (?:\\r ([1-9][0-9]{0,9})|\\n) \\\* ARABIC\z')
    if (-not $sequence.Success -or [long]$sequence.Groups[1].Value -gt 2147483647) { return $false }
    if ($sequence.Groups[2].Success) {
        $start = [long]$sequence.Groups[2].Value
        if ($start -le 65535 -or $start -gt 2147483647) { return $false }
    }
    return $true
}

function Assert-ReportGenWordInternalLinks {
    param($Document)
    foreach ($link in $Document.Hyperlinks) {
        # SubAddress may identify a fragment in an external destination. It is
        # a local bookmark only when the hyperlink has no external Address.
        if (-not $link.Address -and $link.SubAddress -and -not $Document.Bookmarks.Exists($link.SubAddress)) {
            throw "Unresolved internal hyperlink: $($link.SubAddress)"
        }
    }
}

function Assert-ReportGenWordFields {
    param([System.Xml.XmlDocument]$Xml, [System.Xml.XmlNamespaceManager]$Namespaces)
    $sequences = @{}
    foreach ($field in $Xml.SelectNodes('//w:instrText|//w:fldSimple/@w:instr', $Namespaces)) {
        $instructionText = if ($field.NodeType -eq [System.Xml.XmlNodeType]::Attribute) { $field.Value.Trim() } else { $field.InnerText.Trim() }
        if (-not (Test-ReportGenWordFieldInstruction $instructionText)) { throw "Unsupported field instruction." }
        if ($instructionText.StartsWith('SEQ ')) {
            if ($field.NodeType -ne [System.Xml.XmlNodeType]::Attribute -or $field.OwnerElement.LocalName -ne 'fldSimple') {
                throw "Sequence fields must use report-gen's cached simple-field representation."
            }
            $parts = $instructionText.Split(' ')
            $name = $parts[1]
            if ($parts[2] -eq '\r') { $ordinal = [long]$parts[3] }
            else {
                if (-not $sequences.ContainsKey($name)) { throw "Sequence continuation has no preceding start." }
                $ordinal = $sequences[$name] + 1
            }
            $stored = [string]::Concat(@($field.OwnerElement.SelectNodes('.//w:t', $Namespaces) | ForEach-Object { $_.InnerText }))
            if ($ordinal -gt 2147483647 -or $stored -cne [string]$ordinal) { throw "Sequence result does not match its instruction." }
            $sequences[$name] = $ordinal
        }
    }
}

function Get-ReportGenWordContentsMetrics {
    param($Document, [string[]]$ExpectedAnchors)
    $references = @{}
    $referenceCount = 0
    foreach ($field in $Document.Fields) {
        if ($field.Code.Text -match '^\s*PAGEREF\s+"?([A-Za-z_][A-Za-z0-9_]*)"?(?=\s|$)') {
            $anchor = $Matches[1]
            $referenceCount++
            if (-not $references.ContainsKey($anchor)) { $references[$anchor] = 0 }
            $references[$anchor]++
        }
    }
    foreach ($anchor in $ExpectedAnchors) {
        if (-not $references.ContainsKey($anchor) -or $references[$anchor] -ne 1) {
            throw "Contents entry does not retain one native PAGEREF: $anchor"
        }
    }
    # An index of standalone PAGEREFs is not a Word TablesOfContents object.
    # Keep that real object count, separately from entries and live fields.
    return @{
        native_toc_count = $Document.TablesOfContents.Count
        contents_entry_count = $ExpectedAnchors.Count
        page_reference_field_count = $referenceCount
        contents_page_reference_count = $ExpectedAnchors.Count
    }
}

# Run on an interactive Windows machine with a licensed desktop Word installation.
# Work on separate copies; update native page/index fields, save and render.
# Never enable macros or linked resources. Original files remain unchanged.
$ErrorActionPreference = "Stop"
$source = (Resolve-Path -LiteralPath $InputDirectory).Path
$target = [System.IO.Path]::GetFullPath($OutputDirectory)
if ([string]::Equals($source, $target, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Use a separate output directory; source documents are preserved."
}
if ((Test-Path -LiteralPath $target) -and @(Get-ChildItem -LiteralPath $target -Force).Count -gt 0) {
    throw "Use an empty output directory; existing evidence is preserved."
}
New-Item -ItemType Directory -Force -Path $target | Out-Null
$files = @(Get-ChildItem -LiteralPath $source -Filter *.docx -File)
if ($files.Count -eq 0) { throw "No DOCX documents found." }
$sourceProvenance = $null
if ($ExpectedSourceReceipt) {
    # Optional binding to the native-preview receipt exported by report-gen.
    # A LibreOffice receipt establishes source identity, never Word acceptance.
    if ($files.Count -ne 1) { throw "A source receipt binds exactly one DOCX; use an input directory containing only that document." }
    $receiptFile = Get-Item -LiteralPath $ExpectedSourceReceipt
    if ($receiptFile.Length -gt 65536) { throw "Source receipt exceeds 64 KiB." }
    $sourceReceipt = Get-Content -LiteralPath $receiptFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($sourceReceipt.format -cne 'report-gen-docx-native-preview' -or $sourceReceipt.version -ne 1 -or
        $sourceReceipt.source_docx_sha256 -cnotmatch '\A[0-9a-f]{64}\z' -or
        $sourceReceipt.source_revision -isnot [string] -or -not $sourceReceipt.source_revision -or
        $sourceReceipt.word_verified -ne $false) {
        throw "Invalid report-gen native DOCX preview receipt."
    }
    $actualHash = (Get-FileHash -LiteralPath $files[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $sourceReceipt.source_docx_sha256) { throw "DOCX source hash does not match the expected preview receipt." }
    $sourceProvenance = @{
        source_revision = $sourceReceipt.source_revision
        job_id = $sourceReceipt.job_id
        source_docx_sha256 = $actualHash
        receipt_sha256 = (Get-FileHash -LiteralPath $receiptFile.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        binding = 'source_bytes_only_not_renderer_equivalence'
    }
}
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
        $expectedContentsAnchors = @()
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
                        Assert-ReportGenWordFields $xml $ns
                        if ($entry.FullName -eq 'word/document.xml') {
                            $expectedContentsAnchors = @($xml.SelectNodes('//w:sdt[w:sdtPr/w:tag[@w:val="report-gen-contents"]]/w:sdtContent/w:p/w:hyperlink/@w:anchor', $ns) | ForEach-Object { $_.Value })
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
            Assert-ReportGenWordInternalLinks $document
            $document.Repaginate()
            $updateErrors = $document.Fields.Update()
            if ($updateErrors -ne 0) { throw "Word reports a field update error at index $updateErrors." }
            foreach ($toc in $document.TablesOfContents) { $toc.Update() }
            $document.Repaginate()
            foreach ($toc in $document.TablesOfContents) { $toc.UpdatePageNumbers() }
            $document.Save()
            $document.Repaginate()
            Assert-ReportGenWordInternalLinks $document
            $contents = Get-ReportGenWordContentsMetrics $document $expectedContentsAnchors
            $pages = $document.ComputeStatistics(2) # wdStatisticPages
            $pdf = Join-Path $target ($file.BaseName + '-word.pdf')
            $document.ExportAsFixedFormat($pdf, 17) # wdExportFormatPDF
            if ($pages -lt 1 -or -not (Test-Path -LiteralPath $pdf)) { throw "Empty Word rendering." }
            $results += @{file=$file.Name;word_version=$word.Version;word_build=$word.Build;pages=$pages;pdf=[System.IO.Path]::GetFileName($pdf);pdf_sha256=(Get-FileHash -LiteralPath $pdf -Algorithm SHA256).Hash;status="fields_updated_and_rendered";updated_docx=[System.IO.Path]::GetFileName($copy);index_count=$contents.native_toc_count;contents_entry_count=$contents.contents_entry_count;page_reference_field_count=$contents.page_reference_field_count;contents_page_reference_count=$contents.contents_page_reference_count;source_sha256=$beforeHash;updated_sha256=(Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash;source_provenance=$sourceProvenance;native_tables=$document.Tables.Count;native_inline_shapes=$document.InlineShapes.Count;native_hyperlinks=$document.Hyperlinks.Count;native_bookmarks=$document.Bookmarks.Count}
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
    $record = @{schema=2;platform=[Environment]::OSVersion.VersionString;results=$results;recorded_at=[DateTime]::UtcNow.ToString("o");visual_acceptance="pending"}
    $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $target 'word-validation.json') -Encoding UTF8
} finally {
    if ($null -ne $word) {
        if ($null -ne $previousUpdateLinks) { $word.Options.UpdateLinksAtOpen = $previousUpdateLinks }
        $word.Quit(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
    }
}
Write-Output "Word field updates, copy save and rendering completed. Inspect the PDF pages and compare text, commands, images and page references before acceptance."
