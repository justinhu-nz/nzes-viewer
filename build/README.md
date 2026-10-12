# NZES 2023 Explorer — build

`nzes-viewer.html` (one level up) is self-contained: open it in any browser, no internet needed.

To regenerate it after editing `template.html` or `build.py` (needs Python 3 with pandas, and `pdftotext` from poppler):

    cd /Users/admin/Vibes/nzes-viewer
    python3 build/build.py "doi-10.26193-hhmeuz (1)/2_NZES23Release_100227.dta" \
      "doi-10.26193-hhmeuz (1)/1_2023 NZESQuestionnaire_100227.pdf" \
      build/template.html nzes-viewer.html

The HTML embeds respondent-level data (no free text, IDs or electorates), so keep it within the data licence.
