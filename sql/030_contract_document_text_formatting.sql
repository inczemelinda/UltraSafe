-- Convert old contract ASCII tables into prose so existing local databases
-- render like the updated PAD_PROPERTY_RO template.

UPDATE template
SET content = regexp_replace(
    content,
    '\| Categoria[^|]*\|[^|]*\|' || chr(10) ||
    '\|[ \-]+\|[ \-]+\|' || chr(10) ||
    '\| Locuin[^|]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Bunuri mobile[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Total[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|',
    'Suma asigurată totală este de {{coverage.total_sum_insured}} RON.' || chr(10) || chr(10) ||
    'Aceasta este compusă din:' || chr(10) ||
    chr(8226) || ' suma asigurată pentru locuință: {{coverage.building_sum_insured}} RON;' || chr(10) ||
    chr(8226) || ' suma asigurată pentru bunuri mobile: {{coverage.contents_sum_insured}} RON.',
    'g'
)
WHERE content ~ ('\| Categoria[^|]*\|[^|]*\|' || chr(10) || '\|[ \-]+\|[ \-]+\|');

UPDATE quote_document
SET rendered_text = regexp_replace(
    rendered_text,
    '\| Categoria[^|]*\|[^|]*\|' || chr(10) ||
    '\|[ \-]+\|[ \-]+\|' || chr(10) ||
    '\| Locuin[^|]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Bunuri mobile[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Total[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|',
    'Suma asigurată totală este de \3.' || chr(10) || chr(10) ||
    'Aceasta este compusă din:' || chr(10) ||
    chr(8226) || ' suma asigurată pentru locuință: \1;' || chr(10) ||
    chr(8226) || ' suma asigurată pentru bunuri mobile: \2.',
    'g'
)
WHERE rendered_text ~ ('\| Categoria[^|]*\|[^|]*\|' || chr(10) || '\|[ \-]+\|[ \-]+\|');

UPDATE generated_document
SET rendered_text = regexp_replace(
    rendered_text,
    '\| Categoria[^|]*\|[^|]*\|' || chr(10) ||
    '\|[ \-]+\|[ \-]+\|' || chr(10) ||
    '\| Locuin[^|]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Bunuri mobile[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|' || chr(10) ||
    '\| Total[[:blank:]]*\|[[:blank:]]*([^|]+)[[:blank:]]*\|',
    'Suma asigurată totală este de \3.' || chr(10) || chr(10) ||
    'Aceasta este compusă din:' || chr(10) ||
    chr(8226) || ' suma asigurată pentru locuință: \1;' || chr(10) ||
    chr(8226) || ' suma asigurată pentru bunuri mobile: \2.',
    'g'
)
WHERE rendered_text ~ ('\| Categoria[^|]*\|[^|]*\|' || chr(10) || '\|[ \-]+\|[ \-]+\|');
