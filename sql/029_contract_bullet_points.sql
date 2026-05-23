-- Normalize old Markdown-style list markers in contract document data.
-- New seed/template content already uses bullet points, but this keeps
-- existing local databases and generated documents visually consistent.

UPDATE template
SET content = regexp_replace(
    content,
    '(^|' || chr(10) || ')([[:blank:]]*)\* ',
    '\1\2' || chr(8226) || ' ',
    'g'
)
WHERE content ~ ('(^|' || chr(10) || ')([[:blank:]]*)\* ');

UPDATE quote_document
SET rendered_text = regexp_replace(
    rendered_text,
    '(^|' || chr(10) || ')([[:blank:]]*)\* ',
    '\1\2' || chr(8226) || ' ',
    'g'
)
WHERE rendered_text ~ ('(^|' || chr(10) || ')([[:blank:]]*)\* ');

UPDATE generated_document
SET rendered_text = regexp_replace(
    rendered_text,
    '(^|' || chr(10) || ')([[:blank:]]*)\* ',
    '\1\2' || chr(8226) || ' ',
    'g'
)
WHERE rendered_text ~ ('(^|' || chr(10) || ')([[:blank:]]*)\* ');
