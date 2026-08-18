(fileName as text) as table =>
let
    Separator = if Text.EndsWith(SteelFlowExportRoot, "\\") then "" else "\\",
    FilePath = SteelFlowExportRoot & Separator & fileName,
    Source = Csv.Document(
        File.Contents(FilePath),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
in
    PromotedHeaders
