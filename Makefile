PYTHON ?= python3
export MPLCONFIGDIR ?= /tmp/esp-sdr-matplotlib
export TEXMFCACHE ?= /tmp/esp-sdr-tex-cache
export TEXMFVAR ?= /tmp/esp-sdr-tex-var
.PHONY: all reports full twitter images figures check bundle report-sources operational-limit operational-shape operational-ros2 operational-power operational-espnow-long operational-placement coexistence
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
	$(PYTHON) experiments/scripts/render_operational.py --mode limit
	$(PYTHON) experiments/scripts/render_operational.py --mode shape
	$(PYTHON) experiments/scripts/render_ros2.py
	$(PYTHON) experiments/scripts/render_power.py
	$(PYTHON) experiments/scripts/render_long_espnow.py
	$(PYTHON) experiments/scripts/render_placement.py
	$(PYTHON) experiments/scripts/render_bidirectional.py
check:
	$(PYTHON) experiments/scripts/summarize_control.py
	$(PYTHON) experiments/scripts/check_two_team.py
	$(PYTHON) experiments/scripts/check_espnow.py
	$(PYTHON) experiments/scripts/check_operational.py --require-complete limit --require-complete shape
	$(PYTHON) experiments/scripts/check_ros2.py --require-complete
	$(PYTHON) experiments/scripts/check_ros2.py --experiment power --require-complete
	$(PYTHON) experiments/scripts/check_long_espnow.py --require-declared-scope
	$(PYTHON) experiments/scripts/check_long_espnow.py --experiment placement --require-complete
	$(PYTHON) experiments/scripts/check_bidirectional.py
bundle:
	zip -r /tmp/esp-sdr-twitter.zip reports/twitter.tex reports/twitter.pdf reports/images experiments/figures/two-team experiments/figures/espnow experiments/figures/operational experiments/figures/coexistence

report-sources:
	$(PYTHON) experiments/scripts/write_two_team_reports.py
	$(PYTHON) experiments/scripts/write_espnow_reports.py
	$(PYTHON) experiments/scripts/write_operational_notes.py
	$(PYTHON) experiments/scripts/write_operational_reports.py
	$(PYTHON) experiments/scripts/write_bidirectional_reports.py

coexistence:
	$(PYTHON) experiments/scripts/analyze_bidirectional.py
	$(PYTHON) experiments/scripts/analyze_tcp_brackets.py
	$(PYTHON) experiments/scripts/check_bidirectional.py
	$(PYTHON) experiments/scripts/render_bidirectional.py

operational-limit:
	$(PYTHON) experiments/scripts/analyze_operational.py --mode limit
	$(PYTHON) experiments/scripts/check_operational.py --require-complete limit
	$(PYTHON) experiments/scripts/render_operational.py --mode limit

operational-shape:
	$(PYTHON) experiments/scripts/analyze_operational.py --mode shape
	$(PYTHON) experiments/scripts/check_operational.py --require-complete limit --require-complete shape
	$(PYTHON) experiments/scripts/render_operational.py --mode shape

operational-ros2:
	$(PYTHON) experiments/scripts/analyze_ros2.py
	$(PYTHON) experiments/scripts/check_ros2.py --require-complete
	$(PYTHON) experiments/scripts/render_ros2.py

operational-power:
	$(PYTHON) experiments/scripts/analyze_ros2.py --experiment power
	$(PYTHON) experiments/scripts/check_ros2.py --experiment power --require-complete
	$(PYTHON) experiments/scripts/render_power.py

operational-espnow-long:
	$(PYTHON) experiments/scripts/analyze_long_espnow.py
	$(PYTHON) experiments/scripts/check_long_espnow.py --require-declared-scope
	$(PYTHON) experiments/scripts/render_long_espnow.py

operational-placement:
	$(PYTHON) experiments/scripts/analyze_long_espnow.py --experiment placement
	$(PYTHON) experiments/scripts/check_long_espnow.py --experiment placement --require-complete
	$(PYTHON) experiments/scripts/render_placement.py
