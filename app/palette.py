"""G3's colours, shared by the app (app/ui_style.py) and the downloadable report (app/report.py).

60/30/10: cream (page) 60%, navy (sidebar, header, summary cards, text) 30%, coral (buttons, highlights) 10%.

The chart colours are in a fixed order and were checked with the data-visualisation palette checks on the
card colour CARD: lightness band, chroma, colour-blind separation of neighbours (worst 8.9), normal vision
(worst 18.3) and at least 3:1 contrast for every colour. A colour follows the thing it shows (a governorate
or a business group keeps its colour in every chart), never its rank.
"""
NAVY = "#14213D"
CREAM = "#F4EDE0"
CORAL = "#FF6B5B"
CARD = "#FBF7F0"            # panels the charts sit on
INK_MUTED = "#5B6478"       # secondary text (5.1:1 on cream)

CHART_COLOURS = ["#2F5D9E", "#E8594A", "#1E9A84", "#B98414", "#8257B8", "#4F8F2F", "#C2477D", "#2E86C1"]
OTHER_GREY = "#9A9082"      # 'Other categories'
GOV_COLOURS = dict(zip(["Capital", "Muharraq", "Northern", "Southern"], CHART_COLOURS[:4]))
GROUP_COLOURS = dict(zip(["Other Shops", "Restaurants & Cafes", "Supermarkets & Hypermarkets"], CHART_COLOURS[4:7]))
