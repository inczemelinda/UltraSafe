-- Keep PAD property templates on the coverage.* placeholder contract.
-- This is idempotent and also fixes local databases where migration 030
-- already converted the old ASCII table to prose with insured_asset placeholders.

UPDATE template
SET content = replace(
    content,
    'Suma asigurată totală este de {{insured_asset.declared_value}} {{contract_meta.currency}}.' || chr(10) || chr(10) ||
    'Aceasta este compusă din:' || chr(10) ||
    chr(8226) || ' suma asigurată pentru locuință: {{insured_asset.declared_value}} {{contract_meta.currency}};' || chr(10) ||
    chr(8226) || ' suma asigurată pentru bunuri mobile: {{insured_asset.declared_value}} {{contract_meta.currency}}.',
    'Suma asigurată totală este de {{coverage.total_sum_insured}} RON.' || chr(10) || chr(10) ||
    'Aceasta este compusă din:' || chr(10) ||
    chr(8226) || ' suma asigurată pentru locuință: {{coverage.building_sum_insured}} RON;' || chr(10) ||
    chr(8226) || ' suma asigurată pentru bunuri mobile: {{coverage.contents_sum_insured}} RON.'
)
WHERE content LIKE '%{{insured_asset.declared_value}} {{contract_meta.currency}}%';
