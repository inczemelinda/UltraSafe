-- Wording documents are legal-team-authored product terms.
-- They are separate from contract templates and from normalized source laws.
-- Phase 1 only adds first-class wording artifacts and a demo published version;
-- contract generation and legal-review workflows continue to use existing paths.

CREATE TABLE IF NOT EXISTS wording_document (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    product_line TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    language TEXT NOT NULL,
    insurer_id BIGINT REFERENCES insurer(id),
    status TEXT NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS wording_document_version (
    id BIGSERIAL PRIMARY KEY,
    wording_document_id BIGINT NOT NULL REFERENCES wording_document(id) ON DELETE CASCADE,
    version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('draft', 'published', 'superseded', 'archived')
    ),
    full_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    legal_references_json JSONB,
    structured_clauses_json JSONB,
    file_url TEXT,
    effective_from DATE,
    effective_to DATE,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_wording_document_version UNIQUE (wording_document_id, version),
    CONSTRAINT ck_wording_document_version_effective_range CHECK (
        effective_from IS NULL
        OR effective_to IS NULL
        OR effective_to >= effective_from
    )
);

CREATE INDEX IF NOT EXISTS idx_wording_document_product_lookup
    ON wording_document (product_line, jurisdiction, language, status);

CREATE INDEX IF NOT EXISTS idx_wording_document_version_current
    ON wording_document_version (
        wording_document_id,
        status,
        effective_from,
        effective_to,
        published_at
    );

WITH demo_wording AS (
    INSERT INTO wording_document (
        code,
        title,
        product_line,
        jurisdiction,
        language,
        insurer_id,
        status,
        metadata_json,
        created_at,
        updated_at
    )
    VALUES (
        'DEMO_PAD_POLICY_WORDING_RO',
        'PAD Property Insurance Wording RO',
        'property',
        'RO',
        'ro-RO',
        NULL,
        'published',
        '{"is_synthetic":true,"demo_dataset":"wording_phase_1","copied_from_template_code":"DEMO_PAD_POLICY_WORDING_RO"}'::jsonb,
        '2026-05-14T10:00:00+03:00',
        '2026-05-14T10:00:00+03:00'
    )
    ON CONFLICT (code) DO UPDATE SET
        title = EXCLUDED.title,
        product_line = EXCLUDED.product_line,
        jurisdiction = EXCLUDED.jurisdiction,
        language = EXCLUDED.language,
        insurer_id = EXCLUDED.insurer_id,
        status = EXCLUDED.status,
        metadata_json = EXCLUDED.metadata_json,
        updated_at = EXCLUDED.updated_at
    RETURNING id
)
INSERT INTO wording_document_version (
    wording_document_id,
    version,
    status,
    full_text,
    content_hash,
    legal_references_json,
    structured_clauses_json,
    file_url,
    effective_from,
    effective_to,
    published_at,
    created_at,
    updated_at
)
SELECT
    id,
    '1.0',
    'published',
    $wording$CONDIȚII DEMONSTRATIVE DE ASIGURARE PAD PENTRU LOCUINȚE

Document demonstrativ utilizat exclusiv pentru testare și prezentare. Nu reprezintă condiții oficiale de asigurare și nu poate fi folosit pentru emiterea unei polițe reale, pentru soluționarea unei daune reale sau pentru interpretarea drepturilor și obligațiilor prevăzute de legislația aplicabilă.

Versiunea 1.0 - document intern de demonstrație pentru produsul PAD Property Insurance Wording RO.

CAPITOLUL I - DEFINIȚII

1.1. Asigurătorul este entitatea care, în cadrul acestui document demonstrativ, preia riscul producerii evenimentelor asigurate și se obligă să plătească despăgubirea în limitele, condițiile și excluderile prevăzute mai jos.

1.2. Asiguratul este persoana fizică sau juridică menționată în polița demonstrativă, care are un interes patrimonial asupra locuinței asigurate și care datorează prima de asigurare.

1.3. Contractantul este persoana care încheie contractul în nume propriu sau pentru Asigurat și care poate avea obligația de plată a primei, dacă este diferită de Asigurat.

1.4. Locuința asigurată este construcția cu destinație de locuire, identificată prin adresă, număr cadastral sau alte elemente de identificare disponibile, împreună cu elementele constructive care îi asigură funcționalitatea normală.

1.5. Evenimentul asigurat este producerea bruscă, accidentală și independentă de voința Asiguratului a unuia dintre riscurile acoperite, în perioada de valabilitate a contractului.

1.6. Dauna este prejudiciul material direct cauzat locuinței asigurate de un eveniment asigurat, constatat potrivit procedurii din prezentul document demonstrativ.

1.7. Suma asigurată este limita maximă de răspundere a Asigurătorului pentru unul sau mai multe evenimente produse în perioada de asigurare, fără a depăși valoarea menționată în poliță.

1.8. Prima de asigurare este suma datorată de Contractant sau Asigurat pentru preluarea riscului de către Asigurător, potrivit scadențelor indicate în poliță.

1.9. Franșiza este partea din daună suportată de Asigurat, dacă o astfel de franșiză este menționată expres în poliță sau în anexele contractuale.

1.10. Documentele justificative sunt înscrisurile, fotografiile, declarațiile, rapoartele tehnice, devizele, procesele-verbale și orice alte dovezi rezonabil necesare pentru analiza cauzei și întinderii prejudiciului.

CAPITOLUL II - OBIECTUL ASIGURĂRII

2.1. Obiectul asigurării îl constituie protecția locuinței asigurate împotriva riscurilor prevăzute în prezentul document demonstrativ, în limitele sumei asigurate și cu respectarea tuturor condițiilor contractuale.

2.2. Asigurarea acoperă exclusiv prejudiciile materiale directe produse locuinței asigurate. Pierderile indirecte, beneficiile nerealizate, imposibilitatea folosinței, cheltuielile de relocare și pierderile morale sunt acoperite numai dacă sunt menționate expres într-o clauză suplimentară.

2.3. Acoperirea nu transformă prezentul document într-o garanție de întreținere, reparație preventivă, modernizare sau consolidare a imobilului.

2.4. Orice extindere a acoperirii trebuie să fie acceptată în scris de Asigurător și evidențiată în poliță, act adițional sau anexă.

CAPITOLUL III - RISCURI ACOPERITE

3.1. În scop demonstrativ, sunt considerate riscuri acoperite: cutremurul, alunecarea de teren, inundația naturală, incendiul, explozia, trăsnetul, furtuna, grindina și avariile accidentale la instalații, în măsura în care aceste riscuri sunt menționate în polița aferentă.

3.2. Cutremurul este mișcarea seismică a scoarței terestre care produce avarii directe elementelor constructive ale locuinței. Sunt despăgubite avariile care pot fi atribuite în mod rezonabil evenimentului seismic și nu uzurii anterioare.

3.3. Alunecarea de teren este deplasarea naturală a terenului pe care este amplasată locuința, dacă deplasarea are caracter brusc și produce daune directe clădirii.

3.4. Inundația naturală reprezintă acoperirea temporară a terenului cu apă provenită din revărsarea cursurilor de apă, acumulări pluviale excepționale sau alte fenomene naturale similare.

3.5. Incendiul este arderea cu flacără deschisă, produsă accidental, care se poate extinde prin propria forță. Urmele de fum, funingine și intervenția pentru stingerea incendiului sunt analizate împreună cu cauza evenimentului.

3.6. Explozia este eliberarea bruscă de energie provocată de dilatarea gazelor sau vaporilor, dacă aceasta produce avarii directe locuinței asigurate.

3.7. Furtuna și grindina sunt fenomene atmosferice cu intensitate suficientă pentru a provoca avarii directe acoperișului, fațadelor, tâmplăriei exterioare sau altor elemente constructive.

3.8. Avariile accidentale la instalații includ scurgeri bruște și neprevăzute din instalațiile interioare de apă, canalizare sau încălzire, cu condiția ca instalațiile să fi fost întreținute rezonabil.

3.9. Nu se acordă despăgubiri pentru riscuri care nu sunt enumerate, pentru riscuri excluse sau pentru evenimente produse în afara perioadei de valabilitate.

CAPITOLUL IV - BUNURI ASIGURATE

4.1. Sunt asigurate elementele constructive ale locuinței, inclusiv fundația, structura de rezistență, pereții, planșeele, acoperișul, pardoselile, instalațiile încorporate și finisajele fixe.

4.2. Anexele gospodărești, garajele, boxele, împrejmuirile sau alte construcții auxiliare sunt acoperite numai dacă sunt identificate expres în poliță.

4.3. Bunurile mobile aflate în locuință pot fi acoperite doar prin clauză suplimentară. În lipsa unei astfel de clauze, prezentul document demonstrativ privește locuința ca bun imobil.

4.4. Îmbunătățirile aduse locuinței sunt luate în considerare dacă au fost declarate, pot fi dovedite prin documente și nu contravin reglementărilor aplicabile construcției.

CAPITOLUL V - BUNURI EXCLUSE

5.1. Nu sunt asigurate terenul, valoarea de amplasament, culturile agricole, arborii, plantele ornamentale, animalele, autovehiculele, ambarcațiunile, numerarul, titlurile de valoare, metalele prețioase, bijuteriile și colecțiile, dacă nu există o acoperire separată.

5.2. Nu sunt acoperite bunurile aflate în spații comune asupra cărora Asiguratul nu are un drept exclusiv de folosință sau proprietate.

5.3. Nu sunt acoperite construcțiile provizorii, improvizate, neautorizate sau aflate într-o stare avansată de degradare cunoscută anterior încheierii contractului.

5.4. Documentele, arhivele, suporturile electronice de date și programele informatice nu sunt acoperite pentru valoarea informației conținute.

CAPITOLUL VI - EXCLUDERI GENERALE

6.1. Asigurătorul nu datorează despăgubiri pentru daune produse cu intenție de Asigurat, Contractant, beneficiarul despăgubirii sau persoane care acționează cu acordul acestora.

6.2. Sunt excluse daunele cauzate de uzură normală, coroziune, infiltrații lente, igrasie, condens, mucegai, vicii ascunse, defecte de proiectare sau executare și lipsa întreținerii rezonabile.

6.3. Sunt excluse daunele cauzate de lucrări de construcție, renovare, demolare sau intervenții asupra structurii, dacă acestea nu au fost declarate și acceptate de Asigurător.

6.4. Sunt excluse prejudiciile produse de război, invazie, acțiuni militare, revoltă, acte de terorism, contaminare nucleară, confiscare, expropriere sau măsuri dispuse de autorități, cu excepția intervențiilor de urgență pentru limitarea daunei.

6.5. Sunt excluse daunele produse în perioada în care locuința este abandonată, nelocuită în mod permanent sau folosită într-un scop diferit de cel declarat, dacă această împrejurare a contribuit la producerea sau agravarea prejudiciului.

6.6. Nu sunt despăgubite costurile de remediere a unor deficiențe preexistente care ar fi trebuit remediate independent de producerea evenimentului asigurat.

CAPITOLUL VII - SUMA ASIGURATĂ

7.1. Suma asigurată se stabilește la emiterea poliței demonstrative și reprezintă limita maximă de răspundere pentru perioada de asigurare.

7.2. Dacă valoarea reală a prejudiciului depășește suma asigurată, despăgubirea se limitează la suma asigurată, după aplicarea franșizelor, limitelor speciale și excluderilor.

7.3. Dacă locuința este subasigurată față de valoarea sa de reconstrucție, despăgubirea poate fi redusă proporțional, dacă polița prevede expres aplicarea acestei reguli.

7.4. Suma asigurată se poate modifica doar prin acordul părților și, dacă este cazul, prin recalcularea primei.

CAPITOLUL VIII - PRIMA DE ASIGURARE

8.1. Prima de asigurare este datorată la termenele indicate în poliță. Plata primei reprezintă o condiție pentru începerea sau menținerea răspunderii Asigurătorului, dacă polița nu prevede altfel.

8.2. Neplata primei la scadență poate conduce la suspendarea acoperirii, rezilierea contractului sau refuzul despăgubirii pentru evenimente produse după scadență, potrivit clauzelor aplicabile.

8.3. Plata parțială a primei nu obligă Asigurătorul să acopere riscul pentru întreaga perioadă, cu excepția situației în care plata parțială a fost acceptată expres.

8.4. Restituirea primei se poate realiza numai pentru perioada de risc neexpirată și numai dacă nu există daune plătite sau în curs de analiză, cu respectarea prevederilor contractuale.

CAPITOLUL IX - ÎNCEPEREA ȘI ÎNCETAREA RĂSPUNDERII

9.1. Răspunderea Asigurătorului începe la data și ora menționate în poliță, dar nu mai devreme de plata primei sau a primei rate, dacă aceasta este o condiție expresă.

9.2. Răspunderea încetează la expirarea perioadei de asigurare, la rezilierea contractului, la denunțarea acestuia, la epuizarea sumei asigurate sau în alte cazuri prevăzute de contract.

9.3. Evenimentele produse înainte de începutul răspunderii sau după încetarea acesteia nu sunt acoperite, chiar dacă dauna este descoperită ulterior.

9.4. Reînnoirea contractului nu este automată decât dacă polița prevede expres acest lucru și dacă prima aferentă noii perioade este acceptată.

CAPITOLUL X - OBLIGAȚIILE ASIGURATULUI

10.1. Asiguratul are obligația să declare corect informațiile relevante despre locuință, destinația acesteia, anul construcției, structura, starea de întreținere, istoricul daunelor și orice împrejurare care poate influența riscul.

10.2. Asiguratul trebuie să întrețină locuința în stare corespunzătoare, să efectueze reparațiile necesare și să ia măsuri rezonabile pentru prevenirea producerii daunelor.

10.3. Asiguratul trebuie să permită Asigurătorului sau reprezentanților acestuia verificarea locuinței, dacă verificarea este rezonabil necesară pentru evaluarea riscului sau a unei daune.

10.4. În cazul producerii unui eveniment, Asiguratul trebuie să ia măsuri pentru limitarea prejudiciului, fără a modifica nejustificat urmele evenimentului înainte de constatare.

10.5. Asiguratul trebuie să notifice dauna în termen de 10 zile calendaristice de la producerea evenimentului sau de la data la care a luat cunoștință în mod rezonabil de producerea acestuia.

10.6. Notificarea trebuie să cuprindă cel puțin data și locul evenimentului, descrierea împrejurărilor, riscul invocat, estimarea inițială a prejudiciului și datele de contact ale persoanei care gestionează dosarul.

10.7. Asiguratul trebuie să transmită documentele justificative solicitate în mod rezonabil de Asigurător și să ofere explicații complete cu privire la cauza și întinderea daunei.

10.8. Nerespectarea obligațiilor de notificare, conservare a urmelor, transmitere a documentelor sau cooperare poate conduce la reducerea despăgubirii în măsura în care a prejudiciat analiza dosarului.

CAPITOLUL XI - OBLIGAȚIILE ASIGURĂTORULUI

11.1. Asigurătorul are obligația să primească notificarea de daună, să înregistreze dosarul și să comunice Asiguratului documentele rezonabil necesare pentru analiză.

11.2. Asigurătorul trebuie să analizeze dosarul cu bună-credință, pe baza documentelor disponibile, a constatărilor tehnice și a clauzelor aplicabile.

11.3. Asigurătorul trebuie să comunice decizia de admitere, admitere parțială sau respingere a despăgubirii într-un termen rezonabil de la primirea documentației complete.

11.4. În cazul respingerii totale sau parțiale, Asigurătorul va indica motivele principale ale deciziei, clauzele relevante și documentele pe care s-a întemeiat analiza.

CAPITOLUL XII - CONSTATAREA DAUNELOR

12.1. Constatarea daunelor se realizează prin examinarea locuinței, analizarea documentelor, fotografiilor, declarațiilor, rapoartelor tehnice și a altor probe disponibile.

12.2. Asigurătorul poate solicita opinia unui specialist, expert tehnic, evaluator sau prestator de reparații pentru determinarea cauzei, întinderii și valorii prejudiciului.

12.3. Asiguratul nu trebuie să înceapă reparații definitive înainte de constatare, cu excepția măsurilor urgente necesare pentru siguranța persoanelor sau limitarea prejudiciului.

12.4. Dacă reparațiile urgente sunt necesare, Asiguratul trebuie să păstreze dovezi rezonabile, inclusiv fotografii, facturi, devize, piese înlocuite sau declarații ale intervenienților.

12.5. Procesul de constatare nu reprezintă recunoașterea obligației de plată și nu înlătură dreptul Asigurătorului de a verifica acoperirea.

CAPITOLUL XIII - STABILIREA ȘI PLATA DESPĂGUBIRILOR

13.1. Despăgubirea se stabilește în funcție de cauza evenimentului, valoarea prejudiciului direct, limitele de acoperire, franșize, excluderi și documentele justificative.

13.2. Valoarea prejudiciului poate fi calculată pe baza costului rezonabil de readucere a locuinței la starea anterioară producerii evenimentului, fără îmbunătățiri nejustificate.

13.3. Dacă reparația conduce la creșterea valorii locuinței față de starea anterioară, Asigurătorul poate deduce partea corespunzătoare îmbunătățirii, dacă aceasta este identificabilă.

13.4. Despăgubirea nu poate depăși suma asigurată, valoarea reală a prejudiciului și limitele speciale aplicabile fiecărui risc.

13.5. Plata despăgubirii se efectuează către Asigurat, beneficiar, creditor ipotecar sau altă persoană îndreptățită, conform poliței și documentelor prezentate.

13.6. Termenul de plată curge de la data acceptării dosarului și a primirii tuturor documentelor necesare efectuării plății.

13.7. În cazul existenței unor suspiciuni rezonabile privind cauza daunei, întinderea prejudiciului sau dreptul la despăgubire, Asigurătorul poate amâna decizia până la clarificarea situației.

CAPITOLUL XIV - SUBROGARE

14.1. După plata despăgubirii, Asigurătorul se poate subroga, în limita sumei plătite, în drepturile Asiguratului împotriva persoanelor răspunzătoare de producerea prejudiciului.

14.2. Asiguratul trebuie să conserve drepturile de regres ale Asigurătorului și să nu renunțe la acestea fără acordul scris al Asigurătorului.

14.3. Dacă Asiguratul prejudiciază dreptul de subrogare prin acțiuni sau omisiuni imputabile, despăgubirea poate fi redusă proporțional cu prejudiciul cauzat Asigurătorului.

CAPITOLUL XV - ÎNCETAREA CONTRACTULUI

15.1. Contractul încetează la expirarea perioadei de asigurare, prin acordul părților, prin denunțare, prin reziliere pentru neplata primei sau prin epuizarea sumei asigurate.

15.2. Contractul poate înceta înainte de termen dacă riscul încetează să existe, dacă locuința este distrusă total sau dacă informațiile esențiale declarate la încheiere se dovedesc inexacte în mod semnificativ.

15.3. Încetarea contractului nu afectează obligațiile născute anterior încetării, inclusiv obligația de plată a primei scadente și obligația de cooperare în dosarele de daună deschise.

CAPITOLUL XVI - PROTECȚIA DATELOR

16.1. Datele cu caracter personal sunt prelucrate în scopul evaluării riscului, administrării contractului, gestionării daunelor, îndeplinirii obligațiilor legale și apărării drepturilor Asigurătorului.

16.2. Categoriile de date pot include date de identificare, date de contact, informații despre locuință, documente justificative, imagini ale daunelor, date financiare și corespondență privind contractul.

16.3. Datele pot fi comunicate prestatorilor, evaluatorilor, reasigurătorilor, consultanților, autorităților sau altor destinatari atunci când comunicarea este necesară pentru scopurile menționate.

16.4. Persoana vizată poate exercita drepturile prevăzute de legislația aplicabilă privind protecția datelor, în limitele și condițiile acesteia.

CAPITOLUL XVII - LEGEA APLICABILĂ ȘI SOLUȚIONAREA DISPUTELOR

17.1. Prezentul document demonstrativ este redactat pentru un context românesc de prezentare și se raportează generic la cadrul legal aplicabil asigurărilor de locuințe, inclusiv la Legea nr. 260/2008 în măsura relevantă pentru demonstrație.

17.2. Orice neînțelegere privind interpretarea sau executarea contractului se soluționează cu prioritate pe cale amiabilă, prin corespondență scrisă și analizarea documentelor relevante.

17.3. Dacă soluționarea amiabilă nu este posibilă, disputa poate fi înaintată instanțelor competente sau altor mecanisme de soluționare prevăzute de lege și acceptate de părți.

17.4. Reclamațiile privind administrarea contractului sau soluționarea unei daune trebuie să indice polița, dosarul de daună, situația contestată și documentele pe care se întemeiază solicitarea.

CAPITOLUL XVIII - DISPOZIȚII FINALE

18.1. Prezentul document demonstrativ se interpretează împreună cu polița, cererea de asigurare, anexele, actele adiționale și orice clauze speciale acceptate de părți.

18.2. În caz de neconcordanță între o clauză specială și o clauză generală, clauza specială prevalează numai în limita obiectului său expres.

18.3. Orice modificare a contractului trebuie consemnată în scris. Tăcerea, lipsa unui răspuns sau simpla primire a unor documente nu echivalează cu acceptarea unei modificări.

18.4. Nulitatea sau inaplicabilitatea unei clauze nu afectează valabilitatea celorlalte clauze, dacă documentul poate continua să producă efecte fără clauza respectivă.

18.5. Versiunea curentă este destinată testării modificărilor de formulare, evidențierii diferențelor între versiuni și demonstrării fluxurilor interne de analiză juridică.$wording$,
    '2a9480a11038b3b86218dc2e2d93e0d76fbc4d8399839f13a3f6b464d53d22ca',
    '["ro:lege:260:2008","claim_notification_timeline"]'::jsonb,
    NULL,
    NULL,
    '2026-05-14',
    NULL,
    '2026-05-14T10:00:00+03:00',
    '2026-05-14T10:00:00+03:00',
    '2026-05-14T10:00:00+03:00'
FROM demo_wording
ON CONFLICT (wording_document_id, version) DO NOTHING;

