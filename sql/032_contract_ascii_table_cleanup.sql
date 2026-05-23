-- Clean up persisted contract documents that still contain the old ASCII
-- coverage table, including CRLF-rendered rows.

UPDATE template
SET content = regexp_replace(
    content,
    E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|\\s*\\r?\\n\\|\\s*Locuin[^|]*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Bunuri mobile\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Total\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|',
    E'Suma asigurată totală este de {{coverage.total_sum_insured}} RON.\n\nAceasta este compusă din:\n• suma asigurată pentru locuință: {{coverage.building_sum_insured}} RON;\n• suma asigurată pentru bunuri mobile: {{coverage.contents_sum_insured}} RON.',
    'g'
)
WHERE content ~ E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|';

UPDATE generated_document
SET rendered_text = regexp_replace(
    rendered_text,
    E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|\\s*\\r?\\n\\|\\s*Locuin[^|]*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Bunuri mobile\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Total\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|',
    E'Suma asigurată totală este de \\3.\n\nAceasta este compusă din:\n• suma asigurată pentru locuință: \\1;\n• suma asigurată pentru bunuri mobile: \\2.',
    'g'
)
WHERE rendered_text ~ E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|';

UPDATE quote_document
SET rendered_text = regexp_replace(
    rendered_text,
    E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|\\s*\\r?\\n\\|\\s*Locuin[^|]*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Bunuri mobile\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|\\s*\\r?\\n\\|\\s*Total\\s*\\|\\s*([^|\\r\\n]+)\\s*\\|',
    E'Suma asigurată totală este de \\3.\n\nAceasta este compusă din:\n• suma asigurată pentru locuință: \\1;\n• suma asigurată pentru bunuri mobile: \\2.',
    'g'
)
WHERE rendered_text ~ E'\\|\\s*Categoria\\s*\\|[^\\n]*\\|\\s*\\r?\\n\\|\\s*-+\\s*\\|\\s*-+\\s*\\|';
