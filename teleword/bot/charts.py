import io

from teleword.services.stats import Series

BACKGROUND = "#1e262c"
ACCENT = "#43c4e3"
LABELS = "#c4c9cd"


def render_stats_chart(series: Series) -> bytes:
    """Dark-themed weekly chart as PNG bytes.

    Uses `Figure` directly instead of pyplot: no global state, safe to call from worker threads,
    and the figure is garbage-collected after the call.
    """
    # Imported lazily: matplotlib adds ~50 MB to the process, and most updates never draw a chart.
    from matplotlib.figure import Figure

    figure = Figure(figsize=(6.4, 4.8), dpi=100, facecolor=BACKGROUND)
    axes = figure.add_subplot()
    axes.set_facecolor(BACKGROUND)
    axes.grid(visible=True, alpha=0.1)
    axes.tick_params(colors=BACKGROUND, labelcolor=LABELS)
    for spine in axes.spines.values():
        spine.set_color(BACKGROUND)

    x = range(len(series.days))
    axes.fill_between(x, series.mistakes, color=ACCENT, alpha=0.10, label="mistakes")
    axes.fill_between(x, series.first_try, color=ACCENT, alpha=0.18, label="first try")
    axes.fill_between(x, series.points, color=ACCENT, alpha=0.25, label="points")
    axes.plot(
        x, series.points, color=ACCENT, marker=".", markerfacecolor="white", markersize=5, linewidth=1.5
    )

    axes.set_xticks(list(x), series.days)
    top = max([*series.points, *series.mistakes, *series.first_try, 0])
    axes.set_ylim(0, max(top, 30) * 1.1)
    legend = axes.legend(loc="upper left", frameon=False, fontsize=8)
    for text in legend.get_texts():
        text.set_color(LABELS)

    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    return buffer.getvalue()
