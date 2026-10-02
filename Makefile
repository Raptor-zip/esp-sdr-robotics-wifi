PYTHON ?= python3
export MPLCONFIGDIR ?= /tmp/esp-sdr-matplotlib
export TEXMFCACHE ?= /tmp/esp-sdr-tex-cache
export TEXMFVAR ?= /tmp/esp-sdr-tex-var
.PHONY: all reports full twitter images figures check bundle report-sources
all: reports images
reports: full twitter
full:
	mkdir -p $(TEXMFCACHE) $(TEXMFVAR)
	cd reports && lualatex -halt-on-error -interaction=nonstopmode full.tex
	cd reports && lualatex -halt-on-error -interaction=nonstopmode full.tex
twitter:
	mkdir -p $(TEXMFCACHE) $(TEXMFVAR)
	cd reports && lualatex -halt-on-error -interaction=nonstopmode twitter.tex
	cd reports && lualatex -halt-on-error -interaction=nonstopmode twitter.tex
images:
	mkdir -p reports/images
	pdftoppm -png -r 300 reports/twitter.pdf reports/images/page
figures:
	$(PYTHON) experiments/scripts/render_figures.py
	$(PYTHON) experiments/scripts/render_two_team.py
	$(PYTHON) experiments/scripts/render_radio_coexist.py
	$(PYTHON) experiments/scripts/render_espnow.py
check:
	$(PYTHON) experiments/scripts/summarize_control.py
	$(PYTHON) experiments/scripts/check_two_team.py
	$(PYTHON) experiments/scripts/check_espnow.py
bundle:
	zip -r /tmp/esp-sdr-twitter.zip reports/twitter.tex reports/twitter.pdf reports/images experiments/figures/two-team experiments/figures/espnow

report-sources:
	$(PYTHON) experiments/scripts/write_two_team_reports.py
	$(PYTHON) experiments/scripts/write_espnow_reports.py
